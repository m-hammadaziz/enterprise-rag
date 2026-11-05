"""Ingestion: load -> chunk -> embed -> upsert, with versioning and ACLs.

Idempotent by ``source_uri``:
* same content + same ACL -> ``unchanged`` (no re-embedding)
* same content, new ACL    -> ``acl_updated`` (ACL propagated to chunks/records)
* new content              -> ``updated`` (version += 1, chunks replaced atomically)
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from psycopg.types.json import Jsonb

from app.config import settings
from app.db import get_pool
from app.embeddings import embed_texts
from app.ingest.chunker import chunk_blocks
from app.ingest.loaders import LoadedDoc, load_bytes, load_url


@dataclass
class IngestResult:
    document_id: int
    title: str
    status: str
    version: int
    chunks: int
    records: int

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def normalize_groups(groups) -> list[str]:
    if isinstance(groups, str):
        groups = groups.split(",")
    out = sorted({g.strip().lower() for g in (groups or []) if g and g.strip()})
    if not out:
        # Default-deny: a document nobody is allowed to read is a bug, not a default.
        raise ValueError("allowed_groups must contain at least one group")
    return out


# Bump when chunking / record rendering changes so existing documents get re-indexed.
PIPELINE_VERSION = "2"


def _hash(doc: LoadedDoc) -> str:
    """Content hash that also covers everything that changes the stored vectors:
    pipeline version, embedding model and chunking parameters. Switching e.g. from
    the offline hash embedder to bge-small therefore re-embeds on the next ingest."""
    fingerprint = (f"{PIPELINE_VERSION}|{settings.embed_backend}:{settings.embed_model}|"
                   f"{settings.chunk_target_words}/{settings.chunk_overlap_words}|")
    return hashlib.sha256((fingerprint + doc.full_text).encode("utf-8")).hexdigest()


_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_YM = re.compile(r"^(\d{4})-(\d{2})(?:-\d{2})?$")


def _humanize_value(v: str) -> str:
    """'2026-07' -> '2026-07 (July 2026)' so natural-language queries match dates."""
    m = _YM.match(v)
    if m and 1 <= int(m.group(2)) <= 12:
        return f"{v} ({_MONTHS[int(m.group(2)) - 1]} {m.group(1)})"
    return v


def _record_text(dataset: str, row: dict, title: str | None = None) -> str:
    """Row -> searchable sentence-like text. Column names are de-snake-cased so
    'arr_musd' is findable as 'arr', and the dataset title adds context."""
    head = f"{dataset}" + (f" ({title})" if title else "")
    return head + ": " + "; ".join(
        f"{k.replace('_', ' ')}: {_humanize_value(v)}" for k, v in row.items() if v != "")


def ingest_loaded(
    doc: LoadedDoc,
    source_uri: str,
    allowed_groups,
    title: str | None = None,
    metadata: dict | None = None,
) -> IngestResult:
    groups = normalize_groups(allowed_groups)
    title = (title or doc.title).strip()
    content_hash = _hash(doc)
    metadata = metadata or {}

    if doc.doc_type == "csv":
        chunks = []
        dataset = metadata.get("dataset") or Path(source_uri).stem
        rec_texts = [_record_text(dataset, r, title) for r in doc.rows]
    else:
        chunks = chunk_blocks(doc.blocks, settings.chunk_target_words, settings.chunk_overlap_words)
        dataset, rec_texts = None, []
    if not chunks and not rec_texts:
        raise ValueError(f"No extractable text in {source_uri}")

    pool = get_pool()
    with pool.connection() as conn:
        existing = conn.execute(
            "SELECT id, version, content_hash, allowed_groups FROM documents WHERE source_uri = %s",
            (source_uri,),
        ).fetchone()

        if existing and existing["content_hash"] == content_hash:
            status = "unchanged"
            if sorted(existing["allowed_groups"]) != groups:
                set_document_acl(existing["id"], groups, conn=conn)
                status = "acl_updated"
            conn.execute(
                "UPDATE documents SET title=%s, metadata=%s, updated_at=now() WHERE id=%s",
                (title, Jsonb(metadata), existing["id"]),
            )
            n_chunks = conn.execute("SELECT count(*) AS n FROM chunks WHERE document_id=%s",
                                    (existing["id"],)).fetchone()["n"]
            n_recs = conn.execute("SELECT count(*) AS n FROM records WHERE document_id=%s",
                                  (existing["id"],)).fetchone()["n"]
            return IngestResult(existing["id"], title, status, existing["version"], n_chunks, n_recs)

    # Embed outside the transaction (slow on CPU).
    chunk_vecs = embed_texts(
        [f"{title}\n{c.section or ''}\n{c.text}".strip() for c in chunks]
    ) if chunks else []
    rec_vecs = embed_texts(rec_texts) if rec_texts else []

    with pool.connection() as conn, conn.transaction():
        if existing:
            doc_id, version = existing["id"], existing["version"] + 1
            conn.execute(
                """UPDATE documents SET title=%s, doc_type=%s, allowed_groups=%s, version=%s,
                   content_hash=%s, metadata=%s, updated_at=now() WHERE id=%s""",
                (title, doc.doc_type, groups, version, content_hash, Jsonb(metadata), doc_id),
            )
            conn.execute("DELETE FROM chunks WHERE document_id=%s", (doc_id,))
            conn.execute("DELETE FROM records WHERE document_id=%s", (doc_id,))
            status = "updated"
        else:
            row = conn.execute(
                """INSERT INTO documents (title, source_uri, doc_type, allowed_groups, version,
                   content_hash, metadata) VALUES (%s,%s,%s,%s,1,%s,%s) RETURNING id""",
                (title, source_uri, doc.doc_type, groups, content_hash, Jsonb(metadata)),
            ).fetchone()
            doc_id, version, status = row["id"], 1, "created"

        with conn.cursor() as cur:
            if chunks:
                cur.executemany(
                    """INSERT INTO chunks (document_id, chunk_index, content, page, section,
                       allowed_groups, embedding, word_count) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [
                        (doc_id, c.index, c.text, c.page, c.section, groups, np.asarray(vec, dtype=np.float32), c.word_count)
                        for c, vec in zip(chunks, chunk_vecs)
                    ],
                )
            if rec_texts:
                cur.executemany(
                    """INSERT INTO records (document_id, dataset, row_index, data, text_repr,
                       allowed_groups, embedding) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    [
                        (doc_id, dataset, i, Jsonb(r), t, groups, np.asarray(vec, dtype=np.float32))
                        for i, (r, t, vec) in enumerate(zip(doc.rows, rec_texts, rec_vecs))
                    ],
                )
    return IngestResult(doc_id, title, status, version, len(chunks), len(rec_texts))


def set_document_acl(document_id: int, groups, conn=None) -> list[str]:
    """Change who can read a document. Propagates to all chunks/records atomically."""
    groups = normalize_groups(groups)

    def _apply(c):
        with c.transaction():
            n = c.execute("UPDATE documents SET allowed_groups=%s, updated_at=now() WHERE id=%s",
                          (groups, document_id)).rowcount
            if not n:
                raise KeyError(document_id)
            c.execute("UPDATE chunks SET allowed_groups=%s WHERE document_id=%s", (groups, document_id))
            c.execute("UPDATE records SET allowed_groups=%s WHERE document_id=%s", (groups, document_id))

    if conn is not None:
        _apply(conn)
    else:
        with get_pool().connection() as c:
            _apply(c)
    return groups


def ingest_file(path: str | Path, allowed_groups, title: str | None = None,
                metadata: dict | None = None, source_uri: str | None = None) -> IngestResult:
    p = Path(path)
    doc = load_bytes(p.read_bytes(), p.name)
    meta = {"filename": p.name, **(metadata or {})}
    return ingest_loaded(doc, source_uri or p.as_posix(), allowed_groups, title, meta)


def ingest_bytes(data: bytes, filename: str, allowed_groups, title: str | None = None,
                 metadata: dict | None = None, source_uri: str | None = None) -> IngestResult:
    doc = load_bytes(data, filename)
    meta = {"filename": filename, **(metadata or {})}
    return ingest_loaded(doc, source_uri or f"upload://{filename}", allowed_groups, title, meta)


def ingest_url(url: str, allowed_groups, title: str | None = None, metadata: dict | None = None) -> IngestResult:
    doc = load_url(url)
    return ingest_loaded(doc, url, allowed_groups, title, {"url": url, **(metadata or {})})


def ingest_manifest(manifest_path: str | Path) -> list[IngestResult]:
    """Manifest format (JSON):
    {"documents": [{"path": "hr/handbook.pdf", "allowed_groups": ["all-staff"],
                    "title": "...", "metadata": {...}}, {"url": "https://...", ...}]}
    Paths are relative to the manifest file. The document's stable source_uri is
    ``<manifest-dir-name>/<path>`` so re-ingesting from another machine dedupes.
    """
    mp = Path(manifest_path)
    spec = json.loads(mp.read_text(encoding="utf-8"))
    out = []
    for item in spec["documents"]:
        if "url" in item:
            out.append(ingest_url(item["url"], item["allowed_groups"], item.get("title"), item.get("metadata")))
        else:
            fp = mp.parent / item["path"]
            out.append(ingest_file(fp, item["allowed_groups"], item.get("title"), item.get("metadata"),
                                   source_uri=f"{mp.parent.name}/{item['path']}"))
    return out

"""Hybrid retrieval: pgvector (dense) + Postgres full-text (sparse) -> RRF -> rerank.

Access control is enforced *inside every SQL query* with
``allowed_groups && %(groups)s`` - restricted rows never leave the database, so
they cannot leak through the reranker, the LLM prompt, citations or logs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time

import numpy as np

from app.config import settings
from app.db import get_pool
from app.embeddings import embed_query
from app.rerank import rerank_scores

MODES = ("vector", "keyword", "hybrid", "hybrid_rerank")

# table -> (text column, extra select list). Fixed identifiers only (no user input).
_TABLES = {
    "chunks": "content",
    "records": "text_repr",
}

_KEYWORD_TSQUERY = """
  to_tsquery('english', coalesce(array_to_string(ARRAY(
      SELECT quote_literal(l) FROM unnest(tsvector_to_array(to_tsvector('english', %(q)s))) AS l
  ), ' | '), ''))
"""


@dataclass
class Source:
    kind: str                 # "chunk" | "record"
    id: int
    document_id: int
    title: str
    source_uri: str
    doc_type: str
    text: str
    section: str | None = None
    page: int | None = None
    version: int | None = None
    score: float = 0.0        # final score (rerank if available, else fused)
    ranks: dict = field(default_factory=dict)   # diagnostics: per-retriever rank
    sid: str = ""             # citation label assigned by the agent: S1, S2, ...

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.id}"

    def citation(self) -> dict:
        return {
            "sid": self.sid, "kind": self.kind, "id": self.id, "document_id": self.document_id,
            "title": self.title, "source_uri": self.source_uri, "section": self.section,
            "page": self.page, "version": self.version, "score": round(self.score, 4),
            "snippet": self.text[:300],
        }


def _vector(conn, table: str, qvec, groups: list[str], k: int) -> list[int]:
    conn.execute(f"SET LOCAL hnsw.ef_search = {int(settings.hnsw_ef_search)}")
    rows = conn.execute(
        f"""SELECT id FROM {table}
            WHERE allowed_groups && %(groups)s AND embedding IS NOT NULL
            ORDER BY embedding <=> %(qv)s::vector LIMIT %(k)s""",
        {"groups": groups, "qv": np.asarray(qvec, dtype=np.float32), "k": k},
    ).fetchall()
    return [r["id"] for r in rows]


def _keyword(conn, table: str, query: str, groups: list[str], k: int) -> list[int]:
    rows = conn.execute(
        f"""WITH q AS (SELECT {_KEYWORD_TSQUERY} AS tsq)
            SELECT t.id FROM {table} t, q
            WHERE t.allowed_groups && %(groups)s AND t.tsv @@ q.tsq
            ORDER BY ts_rank_cd(t.tsv, q.tsq, 1) DESC, t.id LIMIT %(k)s""",
        {"q": query, "groups": groups, "k": k},
    ).fetchall()
    return [r["id"] for r in rows]


def rrf_fuse(rankings: dict[str, list[int]], k: int = 60) -> list[tuple[int, float, dict]]:
    """Reciprocal Rank Fusion. Returns [(id, score, {retriever: rank})] best first."""
    scores: dict[int, float] = {}
    ranks: dict[int, dict] = {}
    for name, ids in rankings.items():
        for r, _id in enumerate(ids, start=1):
            scores[_id] = scores.get(_id, 0.0) + 1.0 / (k + r)
            ranks.setdefault(_id, {})[name] = r
    order = sorted(scores, key=lambda i: (-scores[i], i))
    return [(i, scores[i], ranks[i]) for i in order]


def _hydrate(conn, table: str, ids: list[int], groups: list[str]) -> dict[int, Source]:
    if not ids:
        return {}
    if table == "chunks":
        sql = """SELECT c.id, c.document_id, c.content AS text, c.section, c.page,
                        d.title, d.source_uri, d.doc_type, d.version
                 FROM chunks c JOIN documents d ON d.id = c.document_id
                 WHERE c.id = ANY(%(ids)s) AND c.allowed_groups && %(groups)s
                   AND d.allowed_groups && %(groups)s"""
        kind = "chunk"
    else:
        sql = """SELECT r.id, r.document_id, r.text_repr AS text, r.dataset AS section,
                        NULL::int AS page, d.title, d.source_uri, d.doc_type, d.version
                 FROM records r JOIN documents d ON d.id = r.document_id
                 WHERE r.id = ANY(%(ids)s) AND r.allowed_groups && %(groups)s
                   AND d.allowed_groups && %(groups)s"""
        kind = "record"
    rows = conn.execute(sql, {"ids": ids, "groups": groups}).fetchall()
    return {r["id"]: Source(kind=kind, **r) for r in rows}


def search(
    query: str,
    groups: list[str],
    table: str = "chunks",
    mode: str = "hybrid_rerank",
    top_k: int | None = None,
    timings: dict | None = None,
) -> list[Source]:
    """Search one data source for a user. ``groups`` = the caller's groups."""
    if table not in _TABLES:
        raise ValueError(f"unknown table {table}")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    top_k = top_k or settings.final_top_k
    groups = sorted({g.lower() for g in groups})
    if not groups or not query.strip():
        return []
    timings = timings if timings is not None else {}
    n = settings.candidates_per_retriever

    t0 = time.perf_counter()
    qvec = embed_query(query) if mode != "keyword" else None
    t1 = time.perf_counter()
    timings["embed_ms"] = timings.get("embed_ms", 0) + (t1 - t0) * 1000

    with get_pool().connection() as conn, conn.transaction():
        rankings: dict[str, list[int]] = {}
        if mode in ("vector", "hybrid", "hybrid_rerank"):
            rankings["vector"] = _vector(conn, table, qvec, groups, n)
        if mode in ("keyword", "hybrid", "hybrid_rerank"):
            rankings["keyword"] = _keyword(conn, table, query, groups, n)
        fused = rrf_fuse(rankings, settings.rrf_k)
        pool_ids = [i for i, _, _ in fused[: max(settings.rerank_pool, top_k)]]
        hydrated = _hydrate(conn, table, pool_ids, groups)
    t2 = time.perf_counter()
    timings["db_ms"] = timings.get("db_ms", 0) + (t2 - t1) * 1000

    cands: list[Source] = []
    for _id, fscore, ranks in fused:
        s = hydrated.get(_id)
        if s is None:
            continue
        s.score, s.ranks = fscore, ranks
        cands.append(s)

    if mode == "hybrid_rerank" and cands:
        scores = rerank_scores(query, [f"{c.title}. {c.section or ''}. {c.text}" for c in cands])
        for c, sc in zip(cands, scores):
            c.ranks["fused_score"] = round(c.score, 5)
            c.score = float(sc)
        cands.sort(key=lambda c: -c.score)
    elif mode == "vector" or mode == "keyword" or mode == "hybrid":
        # Normalise fused scores to 0..1 so the evidence gate has a stable scale.
        if cands:
            top = cands[0].score
            for c in cands:
                c.score = c.score / top if top else 0.0
    timings["rerank_ms"] = timings.get("rerank_ms", 0) + (time.perf_counter() - t2) * 1000
    return cands[:top_k]


def list_documents(groups: list[str], query: str | None = None, limit: int = 20) -> list[dict]:
    """Document catalog visible to the caller (title search optional)."""
    groups = sorted({g.lower() for g in groups})
    if not groups:
        return []
    params: dict = {"groups": groups, "limit": limit}
    where = "allowed_groups && %(groups)s"
    order = "updated_at DESC"
    if query and query.strip():
        params["q"] = query
        where += f" AND (to_tsvector('english', title || ' ' || coalesce(metadata->>'description','')) @@ {_KEYWORD_TSQUERY} OR title ILIKE '%%' || %(q)s || '%%')"
        order = f"ts_rank_cd(to_tsvector('english', title || ' ' || coalesce(metadata->>'description','')), {_KEYWORD_TSQUERY}) DESC, updated_at DESC"
    with get_pool().connection() as conn:
        rows = conn.execute(
            f"""SELECT id, title, source_uri, doc_type, version, updated_at,
                       metadata->>'description' AS description,
                       (SELECT count(*) FROM chunks c WHERE c.document_id = documents.id) AS chunks
                FROM documents WHERE {where} ORDER BY {order} LIMIT %(limit)s""",
            params,
        ).fetchall()
    return [dict(r, updated_at=r["updated_at"].isoformat() if r["updated_at"] else None) for r in rows]

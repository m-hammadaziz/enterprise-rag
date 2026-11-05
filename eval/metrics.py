"""Scoring helpers for the benchmark (pure functions, unit-tested)."""
from __future__ import annotations

import math
import re
from pathlib import Path

from app.textutil import normalize, tokens


def norm(text: str) -> str:
    t = normalize(text)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)        # 1,500 -> 1500
    t = t.replace("%", " percent")
    t = t.replace(" ", " ")
    return " ".join(t.split())


def _alt_in(alt: str, text: str) -> bool:
    a = norm(alt)
    if not a:
        return False
    # Numbers must not match inside larger numbers ("25" must not match "250" or "1.25").
    pat = re.escape(a)
    if a[0].isdigit():
        pat = r"(?<![\d.])" + pat
    if a[-1].isdigit():
        pat = pat + r"(?![\d]|\.\d)"
    return re.search(pat, text) is not None


def fact_present(fact: str, text: str) -> bool:
    """fact = 'alt1|alt2' -> True if any alternative appears in text."""
    t = norm(text)
    return any(_alt_in(alt, t) for alt in fact.split("|"))


def facts_score(facts: list[str], text: str) -> float:
    if not facts:
        return 1.0
    return sum(fact_present(f, text) for f in facts) / len(facts)


def slug_of(source_uri: str) -> str:
    return Path(source_uri.split("://")[-1]).stem


def evidence_in(evidence: str, source_text: str, min_token_recall: float = 0.85) -> bool:
    """Is this evidence string contained in the source? Exact (normalised) match, or
    high token recall to tolerate PDF line-wrapping / table rendering differences."""
    e, s = norm(evidence), norm(source_text)
    if e in s:
        return True
    et = tokens(evidence, drop_stopwords=False)
    if not et:
        return False
    st = set(tokens(source_text, drop_stopwords=False))
    return sum(t in st for t in et) / len(et) >= min_token_recall


def retrieval_metrics(results: list[dict], evidence: list[str], relevant_docs: list[str], ks=(1, 3, 5, 10)) -> dict:
    """results: ranked [{'text':..., 'source_uri':...}]. Binary relevance per result."""
    rel = [any(evidence_in(e, r["text"]) for e in evidence) for r in results]
    out: dict = {}
    for k in ks:
        top = results[:k]
        covered = [any(evidence_in(e, r["text"]) for r in top) for e in evidence]
        out[f"hit@{k}"] = float(any(rel[:k]))
        out[f"recall@{k}"] = sum(covered) / len(evidence) if evidence else 0.0
        out[f"doc_hit@{k}"] = float(any(slug_of(r["source_uri"]) in relevant_docs for r in top))
    first = next((i for i, r in enumerate(rel[:10]) if r), None)
    out["mrr@10"] = 1.0 / (first + 1) if first is not None else 0.0
    dcg = sum(1.0 / math.log2(i + 2) for i, r in enumerate(rel[:10]) if r)
    n_rel = min(max(sum(rel), len(evidence)), 10)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(n_rel))
    out["ndcg@10"] = dcg / idcg if idcg else 0.0
    return out


def citation_metrics(citations: list[dict], sources_by_sid: dict[str, dict], evidence: list[str],
                     relevant_docs: list[str]) -> dict:
    """Precision: share of citations pointing at a supporting source.
    Recall: share of evidence strings covered by at least one cited source."""
    if not citations:
        return {"cit_precision": 0.0, "cit_doc_precision": 0.0, "cit_recall": 0.0, "n_citations": 0}
    texts = [sources_by_sid.get(c["sid"], {}).get("text") or c.get("snippet", "") for c in citations]
    if evidence:
        sup = [any(evidence_in(e, t) for e in evidence) for t in texts]
        rec = sum(any(evidence_in(e, t) for t in texts) for e in evidence) / len(evidence)
    else:  # catalog questions: document-level only
        sup = [slug_of(c["source_uri"]) in relevant_docs for c in citations]
        rec = float(any(sup))
    doc_ok = [slug_of(c["source_uri"]) in relevant_docs for c in citations]
    return {
        "cit_precision": sum(sup) / len(sup),
        "cit_doc_precision": sum(doc_ok) / len(doc_ok),
        "cit_recall": rec,
        "n_citations": len(citations),
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return v[int(k)] if f == c else v[f] + (v[c] - v[f]) * (k - f)

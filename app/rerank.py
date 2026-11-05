"""Second-stage rerankers. All return scores normalised to 0..1 (higher = better)."""
from __future__ import annotations

import math
from functools import lru_cache

from app.config import settings
from app.textutil import tokens


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


@lru_cache(maxsize=1)
def _cross_encoder():
    import torch
    from sentence_transformers import CrossEncoder  # lazy

    # Force raw logits on every sentence-transformers version; we apply the
    # sigmoid ourselves so thresholds are comparable across models.
    try:
        return CrossEncoder(settings.rerank_model, max_length=512, activation_fn=torch.nn.Identity())
    except TypeError:  # sentence-transformers < 4
        return CrossEncoder(
            settings.rerank_model, max_length=512, default_activation_function=torch.nn.Identity()
        )


def lexical_scores(query: str, passages: list[str]) -> list[float]:
    """IDF-weighted query-term coverage (+ bigram bonus), computed over the
    candidate pool. Cheap stand-in for a cross-encoder when models are unavailable."""
    q = list(dict.fromkeys(tokens(query)))
    if not q or not passages:
        return [0.0] * len(passages)
    docs = [tokens(p) for p in passages]
    sets = [set(d) for d in docs]
    n = len(docs)
    # Smoothed IDF over a pool that is mostly relevant -> keep a floor so common
    # but meaningful terms still count.
    idf = {t: max(0.3, math.log((n + 1) / (1 + sum(t in s for s in sets))) + 0.5) for t in q}
    total = sum(idf.values())
    q_bigrams = set(zip(q, q[1:]))
    out = []
    for d, s in zip(docs, sets):
        cov = sum(idf[t] for t in q if t in s) / total
        bigrams = set(zip(d, d[1:]))
        bonus = 0.1 * (len(q_bigrams & bigrams) / len(q_bigrams)) if q_bigrams else 0.0
        out.append(min(1.0, cov + bonus))
    return out


def rerank_scores(query: str, passages: list[str]) -> list[float]:
    if not passages:
        return []
    backend = settings.rerank_backend
    if backend == "cross-encoder":
        raw = _cross_encoder().predict([(query, p) for p in passages], batch_size=16)
        return [_sigmoid(float(x)) for x in raw]
    if backend == "lexical":
        return lexical_scores(query, passages)
    return [0.0] * len(passages)

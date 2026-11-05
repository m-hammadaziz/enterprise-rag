"""Embedding backends.

* ``sentence-transformers`` (default): BAAI/bge-small-en-v1.5, 384-d, normalised.
* ``hash``: deterministic hashed word + character-trigram vectors. No download, no
  GPU, ~lexical quality. Used for tests/CI and environments without model access.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache

import numpy as np

from app.config import settings
from app.textutil import normalize, tokens

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class HashEmbedder:
    def __init__(self, dim: int):
        self.dim = dim

    def _bucket(self, feat: str) -> tuple[int, float]:
        h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % self.dim
        sign = 1.0 if h[4] & 1 else -1.0
        return idx, sign

    def encode_one(self, text: str) -> list[float]:
        v = np.zeros(self.dim, dtype=np.float32)
        toks = tokens(text)
        for t in toks:
            i, s = self._bucket("w:" + t)
            v[i] += 2.0 * s
        for a, b in zip(toks, toks[1:]):
            i, s = self._bucket(f"b:{a}_{b}")
            v[i] += 1.0 * s
        flat = " ".join(normalize(text).split())
        for j in range(len(flat) - 2):
            i, s = self._bucket("c:" + flat[j : j + 3])
            v[i] += 0.15 * s
        n = np.linalg.norm(v)
        return (v / n if n else v).tolist()

    def encode(self, texts: list[str]) -> list[list[float]]:
        return [self.encode_one(t) for t in texts]


@lru_cache(maxsize=1)
def _backend():
    if settings.embed_backend == "hash":
        return HashEmbedder(settings.embed_dim)
    from sentence_transformers import SentenceTransformer  # heavy import, lazy

    return SentenceTransformer(settings.embed_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _backend()
    if isinstance(model, HashEmbedder):
        return model.encode(texts)
    return model.encode(texts, normalize_embeddings=True, batch_size=32).tolist()


def embed_query(q: str) -> list[float]:
    model = _backend()
    if isinstance(model, HashEmbedder):
        return model.encode_one(q)
    # bge models work best with this prefix on queries only (not on documents)
    prefix = BGE_QUERY_PREFIX if "bge" in settings.embed_model.lower() else ""
    return model.encode(prefix + q, normalize_embeddings=True).tolist()

"""Small, dependency-free text helpers shared by the offline backends and eval."""
from __future__ import annotations

import re
import unicodedata

STOPWORDS = frozenset(
    """a about above after again against all am an and any are as at be because been
    before being below between both but by can could did do does doing down during each
    few for from further had has have having he her here hers herself him himself his how
    i if in into is it its itself just me more most my myself no nor not now of off on
    once only or other our ours ourselves out over own same she should so some such than
    that the their theirs them themselves then there these they this those through to too
    under until up very was we were what when where which while who whom why will with
    would you your yours yourself yourselves tell please according company our us does
    much many get got need know find give""".split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    return text


def stem(tok: str) -> str:
    """Very light suffix stripping - good enough for lexical matching."""
    for suf in ("ations", "ation", "ings", "ing", "ies", "ied", "es", "ed", "s"):
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            if suf in ("ies", "ied"):
                return tok[: -len(suf)] + "y"
            return tok[: -len(suf)]
    return tok


def tokens(text: str, drop_stopwords: bool = True) -> list[str]:
    toks = _TOKEN_RE.findall(normalize(text).replace(",", ""))
    if drop_stopwords:
        toks = [t for t in toks if t not in STOPWORDS]
    return [stem(t) for t in toks]


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(\[])|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) > 2]

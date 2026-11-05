"""Structure-aware chunking.

* Never merges text across a section (heading) boundary or a PDF page boundary,
  so every chunk has one unambiguous citation target (title / section / page).
* Packs paragraphs up to ``target_words``; splits over-long paragraphs on sentences.
* Carries ``overlap_words`` of trailing sentences into the next chunk of the same section.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.ingest.loaders import Block
from app.textutil import split_sentences


@dataclass
class Chunk:
    index: int
    text: str
    page: int | None
    section: str | None

    @property
    def word_count(self) -> int:
        return len(self.text.split())


def _split_long(text: str, target: int) -> list[str]:
    sents = split_sentences(text)
    out, cur, n = [], [], 0
    for s in sents:
        w = len(s.split())
        if cur and n + w > target:
            out.append(" ".join(cur))
            cur, n = [], 0
        cur.append(s)
        n += w
    if cur:
        out.append(" ".join(cur))
    return out or [text]


def _tail(text: str, words: int) -> str:
    if words <= 0:
        return ""
    sents = split_sentences(text)
    tail: list[str] = []
    n = 0
    for s in reversed(sents):
        n += len(s.split())
        if n > words and tail:
            break
        tail.insert(0, s)
        if n >= words:
            break
    t = " ".join(tail)
    return t if len(t.split()) <= words * 2 else ""


def chunk_blocks(blocks: list[Block], target_words: int = 180, overlap_words: int = 30) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_words = 0
    key: tuple | None = None        # (section, page) of the current buffer
    has_body = False

    def flush(carry: bool) -> str:
        nonlocal buf, buf_words, has_body
        carried = ""
        if buf and has_body:
            text = "\n".join(buf).strip()
            chunks.append(Chunk(len(chunks), text, key[1] if key else None, key[0] if key else None))
            carried = _tail(text, overlap_words) if carry else ""
        buf, buf_words, has_body = [], 0, False
        return carried

    for b in blocks:
        k = (b.section, b.page)
        if key is not None and k != key:
            flush(carry=False)
        key = k
        if b.is_heading:
            # headings are kept as context at the top of the chunk
            if has_body:
                flush(carry=False)
            buf.append(b.text)
            buf_words += len(b.text.split())
            continue
        pieces = _split_long(b.text, target_words) if len(b.text.split()) > target_words else [b.text]
        for piece in pieces:
            w = len(piece.split())
            if has_body and buf_words + w > target_words:
                carried = flush(carry=True)
                if carried:
                    buf.append(carried)
                    buf_words = len(carried.split())
            buf.append(piece)
            buf_words += w
            has_body = True
    flush(carry=False)
    return chunks

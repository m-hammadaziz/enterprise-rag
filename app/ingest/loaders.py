"""Format-specific loaders.

Each loader returns a ``LoadedDoc`` whose ``blocks`` keep the structure we need
for good chunks and good citations: page number (PDF) and heading path (DOCX,
HTML, Markdown). CSV files become structured ``rows`` instead of text blocks.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

SUPPORTED = {".pdf": "pdf", ".docx": "docx", ".html": "html", ".htm": "html",
             ".md": "md", ".markdown": "md", ".txt": "txt", ".csv": "csv"}


@dataclass
class Block:
    text: str
    page: int | None = None
    section: str | None = None   # "Heading > Subheading"
    is_heading: bool = False


@dataclass
class LoadedDoc:
    title: str
    doc_type: str
    blocks: list[Block] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)   # CSV only

    @property
    def full_text(self) -> str:
        if self.rows:
            return "\n".join(str(r) for r in self.rows)
        return "\n".join(b.text for b in self.blocks)


class UnsupportedFormat(ValueError):
    pass


def _clean(text: str) -> str:
    text = text.replace(" ", " ").replace("­", "")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


class _Sections:
    """Tracks a heading path like ['Leave', 'Annual leave']."""

    def __init__(self):
        self.path: list[tuple[int, str]] = []

    def push(self, level: int, title: str) -> None:
        self.path = [(l, t) for l, t in self.path if l < level] + [(level, title)]

    @property
    def current(self) -> str | None:
        return " > ".join(t for _, t in self.path) or None


# ---------------------------------------------------------------- PDF ---------
_NUMBERED_HEADING = re.compile(r"^(\d+(\.\d+)*)\.?\s+[A-Z][^.!?]{2,80}$")


def load_pdf(data: bytes, fallback_title: str) -> LoadedDoc:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    meta_title = (reader.metadata.title if reader.metadata else None) or None
    secs = _Sections()
    blocks: list[Block] = []
    for pno, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        # Re-join hard-wrapped lines into paragraphs; keep heading-looking lines apart.
        para: list[str] = []

        def flush():
            if para:
                blocks.append(Block(_clean(" ".join(para)), page=pno, section=secs.current))
                para.clear()

        for line in raw.splitlines():
            s = _clean(line)
            if not s:
                flush()
                continue
            if _NUMBERED_HEADING.match(s) or (s.isupper() and 3 < len(s) < 80):
                flush()
                secs.push(s.count(".") + 1 if s[0].isdigit() else 1, s)
                blocks.append(Block(s, page=pno, section=secs.current, is_heading=True))
                continue
            para.append(s)
            if s.endswith((".", ":", "?", "!")) and len(" ".join(para)) > 400:
                flush()
        flush()
    title = meta_title or (blocks[0].text if blocks and len(blocks[0].text) < 120 else fallback_title)
    for b in blocks[:3]:  # the printed title line is a heading, not body text
        if b.text.strip().lower() == title.strip().lower():
            b.is_heading = True
    return LoadedDoc(title=title, doc_type="pdf", blocks=blocks)


# --------------------------------------------------------------- DOCX ---------
def load_docx(data: bytes, fallback_title: str) -> LoadedDoc:
    import docx  # python-docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(io.BytesIO(data))
    title = (d.core_properties.title or "").strip() or None
    secs = _Sections()
    blocks: list[Block] = []
    body = d.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            text = _clean(p.text)
            if not text:
                continue
            style = (p.style.name if p.style is not None else "") or ""
            if style == "Title":
                title = title or text
                continue
            m = re.match(r"Heading (\d)", style)
            if m:
                secs.push(int(m.group(1)), text)
                blocks.append(Block(text, section=secs.current, is_heading=True))
            else:
                prefix = "- " if "List" in style else ""
                blocks.append(Block(prefix + text, section=secs.current))
        elif tag == "tbl":
            t = Table(child, d)
            rows = [[_clean(c.text) for c in r.cells] for r in t.rows]
            if not rows:
                continue
            header = rows[0]
            lines = []
            for r in rows[1:]:
                lines.append("; ".join(f"{h}: {v}" for h, v in zip(header, r) if v))
            blocks.append(Block("\n".join(lines) or " | ".join(header), section=secs.current))
    return LoadedDoc(title=title or fallback_title, doc_type="docx", blocks=blocks)


# --------------------------------------------------------------- HTML ---------
def load_html(data: bytes | str, fallback_title: str) -> LoadedDoc:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(data, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg"]):
        tag.decompose()
    title = None
    if soup.title and soup.title.string:
        title = _clean(soup.title.string)
    root = soup.find("main") or soup.find("article") or soup.body or soup
    secs = _Sections()
    blocks: list[Block] = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "tr", "pre", "blockquote", "dd"]):
        # skip containers whose text is already captured by a child we will visit
        if el.name in ("li", "dd") and el.find(["p", "li"]):
            continue
        if el.name == "tr":
            cells = [_clean(c.get_text(" ")) for c in el.find_all(["th", "td"])]
            text = " | ".join(c for c in cells if c)
        else:
            text = _clean(el.get_text(" "))
        if not text:
            continue
        if el.name in ("h1", "h2", "h3", "h4"):
            level = int(el.name[1])
            if level == 1 and not title:
                title = text
            secs.push(level, text)
            blocks.append(Block(text, section=secs.current, is_heading=True))
        else:
            blocks.append(Block(("- " if el.name == "li" else "") + text, section=secs.current))
    return LoadedDoc(title=title or fallback_title, doc_type="html", blocks=blocks)


# ----------------------------------------------------------- Markdown ---------
_MD_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def load_markdown(text: str, fallback_title: str, doc_type: str = "md") -> LoadedDoc:
    secs = _Sections()
    blocks: list[Block] = []
    title = None
    para: list[str] = []

    def flush():
        if para:
            blocks.append(Block(_clean(" ".join(para)), section=secs.current))
            para.clear()

    for line in text.splitlines():
        m = _MD_HEADING.match(line.strip())
        if m and doc_type == "md":
            flush()
            level, head = len(m.group(1)), _clean(m.group(2))
            if level == 1 and not title:
                title = head
            secs.push(level, head)
            blocks.append(Block(head, section=secs.current, is_heading=True))
        elif not line.strip():
            flush()
        elif re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            flush()
            blocks.append(Block(_clean(line.strip()), section=secs.current))
        else:
            para.append(line.strip())
    flush()
    return LoadedDoc(title=title or fallback_title, doc_type=doc_type, blocks=blocks)


# ---------------------------------------------------------------- CSV ---------
def load_csv(text: str, fallback_title: str) -> LoadedDoc:
    reader = csv.DictReader(io.StringIO(text))
    rows = [{(k or "").strip(): (v or "").strip() for k, v in r.items()} for r in reader]
    return LoadedDoc(title=fallback_title, doc_type="csv", rows=rows)


# ------------------------------------------------------------- dispatch -------
def _title_from_name(name: str) -> str:
    return re.sub(r"[-_]+", " ", Path(name).stem).strip().title()


def load_bytes(data: bytes, filename: str) -> LoadedDoc:
    ext = Path(filename).suffix.lower()
    kind = SUPPORTED.get(ext)
    fallback = _title_from_name(filename)
    if kind == "pdf":
        return load_pdf(data, fallback)
    if kind == "docx":
        return load_docx(data, fallback)
    if kind == "html":
        return load_html(data, fallback)
    text = data.decode("utf-8", errors="replace")
    if kind in ("md", "txt"):
        return load_markdown(text, fallback, doc_type=kind)
    if kind == "csv":
        return load_csv(text, fallback)
    raise UnsupportedFormat(f"Unsupported file type: {ext or filename}")


def _reject_private_host(url: str) -> None:
    """Basic SSRF guard for the /ingest/url endpoint."""
    import ipaddress
    import socket
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise ValueError(f"Cannot resolve host {host!r}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError(f"Refusing to fetch internal address {ip} ({host})")


def load_url(url: str, timeout: float = 20.0) -> LoadedDoc:
    import httpx

    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs are supported")
    _reject_private_host(url)
    r = httpx.get(url, timeout=timeout, follow_redirects=True,
                  headers={"User-Agent": "enterprise-rag-ingest/1.0"})
    r.raise_for_status()
    ctype = r.headers.get("content-type", "")
    name = url.rstrip("/").rsplit("/", 1)[-1] or "page"
    if "pdf" in ctype:
        return load_pdf(r.content, _title_from_name(name))
    if "html" in ctype or not ctype:
        return load_html(r.text, url)
    return load_markdown(r.text, _title_from_name(name), doc_type="txt")

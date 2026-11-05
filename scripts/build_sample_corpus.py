"""Render the synthetic Corvane corpus into real PDF / DOCX / HTML / MD / CSV files
plus manifest.json and users.json under data/sample/.

    python -m scripts.build_sample_corpus
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from scripts.sample_corpus import CSVS, DOCS, USERS

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"


def parse(body: str):
    """Yield (kind, payload): ('h', (level, text)), ('p', text), ('li', text), ('table', rows)."""
    lines = body.strip().splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        if ln.startswith("#"):
            level = len(ln) - len(ln.lstrip("#"))
            yield "h", (level, ln.lstrip("#").strip())
        elif ln.startswith("- "):
            yield "li", ln[2:].strip()
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            yield "table", rows
            continue
        else:
            yield "p", ln.strip()
        i += 1


# ------------------------------------------------------------------ renderers --
def to_md(d) -> str:
    return d["body"].strip() + "\n"


def to_html(d) -> str:
    out = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(d['title'])}</title></head><body>",
           "<nav><a href='/'>Intranet home</a> | <a href='/policies'>Policies</a></nav><main>"]
    in_list = False
    for kind, x in parse(d["body"]):
        if kind != "li" and in_list:
            out.append("</ul>")
            in_list = False
        if kind == "h":
            out.append(f"<h{x[0]}>{html.escape(x[1])}</h{x[0]}>")
        elif kind == "p":
            out.append(f"<p>{html.escape(x)}</p>")
        elif kind == "li":
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{html.escape(x)}</li>")
        elif kind == "table":
            out.append("<table>")
            for j, r in enumerate(x):
                tag = "th" if j == 0 else "td"
                out.append("<tr>" + "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in r) + "</tr>")
            out.append("</table>")
    if in_list:
        out.append("</ul>")
    out.append("</main><footer>Corvane Systems intranet - internal use only</footer></body></html>")
    return "\n".join(out)


def to_docx(d, path: Path) -> None:
    import docx

    doc = docx.Document()
    doc.core_properties.title = d["title"]
    for kind, x in parse(d["body"]):
        if kind == "h":
            if x[0] == 1:
                doc.add_heading(x[1], level=0)  # "Title" style
            else:
                doc.add_heading(x[1], level=x[0] - 1)
        elif kind == "p":
            doc.add_paragraph(x)
        elif kind == "li":
            doc.add_paragraph(x, style="List Bullet")
        elif kind == "table":
            t = doc.add_table(rows=len(x), cols=len(x[0]))
            t.style = "Table Grid"
            for r, row in enumerate(x):
                for c, val in enumerate(row):
                    t.cell(r, c).text = val
    doc.save(path)


def to_pdf(d, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    ss = getSampleStyleSheet()
    flow = []
    for kind, x in parse(d["body"]):
        if kind == "h":
            style = ss["Title"] if x[0] == 1 else ss["Heading2"]
            flow.append(Paragraph(html.escape(x[1]), style))
        elif kind == "p":
            flow.append(Paragraph(html.escape(x), ss["BodyText"]))
            flow.append(Spacer(1, 6))
        elif kind == "li":
            flow.append(Paragraph("&bull; " + html.escape(x), ss["BodyText"]))
    SimpleDocTemplate(str(path), pagesize=A4, title=d["title"], author="Corvane Systems").build(flow)


EXT = {"pdf": ".pdf", "docx": ".docx", "html": ".html", "md": ".md"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for d in DOCS:
        sub = OUT / "docs"
        sub.mkdir(exist_ok=True)
        path = sub / f"{d['slug']}{EXT[d['fmt']]}"
        if d["fmt"] == "md":
            path.write_text(to_md(d), encoding="utf-8")
        elif d["fmt"] == "html":
            path.write_text(to_html(d), encoding="utf-8")
        elif d["fmt"] == "docx":
            to_docx(d, path)
        else:
            to_pdf(d, path)
        manifest.append({"path": path.relative_to(OUT).as_posix(), "allowed_groups": d["groups"],
                         "title": d["title"], "metadata": {"slug": d["slug"], "description": d["description"]}})
    for c in CSVS:
        sub = OUT / "datasets"
        sub.mkdir(exist_ok=True)
        path = sub / f"{c['slug']}.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(c["header"])
            w.writerows(c["rows"])
        manifest.append({"path": path.relative_to(OUT).as_posix(), "allowed_groups": c["groups"],
                         "title": c["title"],
                         "metadata": {"slug": c["slug"], "dataset": c["slug"], "description": c["description"]}})
    (OUT / "manifest.json").write_text(json.dumps({"documents": manifest}, indent=2), encoding="utf-8")
    (OUT / "users.json").write_text(json.dumps({"_note": "Demo users and keys for local development only.",
                                                "users": USERS}, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest)} files + manifest.json + users.json to {OUT}")


if __name__ == "__main__":
    main()

"""Ingest documents from the command line.

Examples
  python -m scripts.ingest --manifest data/sample/manifest.json
  python -m scripts.ingest --path data/raw/handbook.pdf --groups all-staff
  python -m scripts.ingest --path data/raw/engineering --groups engineering   # whole folder
  python -m scripts.ingest --url https://example.com/page --groups all-staff
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app.ingest.loaders import SUPPORTED
from app.ingest.pipeline import ingest_file, ingest_manifest, ingest_url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest")
    src.add_argument("--path")
    src.add_argument("--url")
    ap.add_argument("--groups", help="comma-separated allowed groups (required for --path/--url)")
    ap.add_argument("--title")
    a = ap.parse_args(argv)

    if a.manifest:
        results = ingest_manifest(a.manifest)
    else:
        if not a.groups:
            ap.error("--groups is required (documents are default-deny)")
        if a.url:
            results = [ingest_url(a.url, a.groups, a.title)]
        else:
            p = Path(a.path)
            files = [p] if p.is_file() else sorted(f for f in p.rglob("*") if f.suffix.lower() in SUPPORTED)
            results = []
            for f in files:
                try:
                    results.append(ingest_file(f, a.groups, a.title if p.is_file() else None))
                except Exception as e:  # keep going on bad files
                    print(f"  ! {f}: {e}", file=sys.stderr)
    for r in results:
        print(f"[{r.status:>11}] #{r.document_id} v{r.version} {r.title!r}: {r.chunks} chunks, {r.records} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

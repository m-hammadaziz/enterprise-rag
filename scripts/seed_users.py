"""Create demo users/groups (and their API keys) from data/sample/users.json.

The demo keys in users.json are for local development only. For real users run
  python -m scripts.seed_users --name jane --groups all-staff,finance
which prints a freshly generated key once.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.auth import upsert_user

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "sample" / "users.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(DEFAULT))
    ap.add_argument("--name")
    ap.add_argument("--groups")
    ap.add_argument("--admin", action="store_true")
    a = ap.parse_args(argv)
    if a.name:
        key = upsert_user(a.name, (a.groups or "").split(","), a.admin)
        print(f"{a.name}: {key}")
        return 0
    for u in json.loads(Path(a.file).read_text())["users"]:
        upsert_user(u["name"], u["groups"], u.get("is_admin", False), u.get("demo_api_key"))
        print(f"{u['name']:<8} groups={','.join(u['groups']):<55} key={u.get('demo_api_key')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

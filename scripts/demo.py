"""Live demo against a running API (uvicorn app.main:app).

    python -m scripts.demo                      # http://localhost:8000
    python -m scripts.demo --base http://host:8000 --json demo.json

Walks through: cited answers, permission-aware answers, abstention, structured
data, the catalog, and a live upload -> permission change -> delete cycle.
"""
from __future__ import annotations

import argparse
import json
import textwrap

import httpx

SCENES = [
    ("Cited answer from a PDF", "alice", "How many days of paid annual leave do full-time employees get?"),
    ("Cited answer from a DOCX", "bob", "What is the nightly hotel limit in high-cost cities like London?"),
    ("Finance user asks about finance data", "bob", "What was total revenue in Q3 2026?"),
    ("Same question, engineer without finance access", "alice", "What was total revenue in Q3 2026?"),
    ("Executive asks about a confidential board memo", "erin", "What is the proposed purchase price for Project Atlas?"),
    ("Same question, non-executive", "dave", "What is the proposed purchase price for Project Atlas?"),
    ("Answer from a CSV dataset (structured tool)", "dave", "What is the headcount of the Lisbon office?"),
    ("Question nothing in the corpus answers", "alice", "What is the Wi-Fi password for the Berlin office?"),
    ("Contractor asks about the security policy", "frank", "Within how many days must new joiners complete security training?"),
]


def show(title: str, user: str, q: str, r: dict) -> dict:
    print(f"\n━━ {title}\n   user: {user}   Q: {q}")
    status = "ABSTAINED" if r["abstained"] else "ANSWERED"
    print(f"   {status} in {r['timings']['total_ms']:.0f} ms  (tools: {', '.join(t['name'] for t in r['tool_calls'])})")
    print(textwrap.indent(textwrap.fill(r["answer"], 96), "   │ "))
    for c in r["citations"]:
        loc = " · ".join(x for x in [c.get("section"), c.get("page") and f"p.{c['page']}"] if x)
        print(f"   └ [{c['sid']}] {c['title']}  ({loc})")
    return {"title": title, "user": user, "question": q, **{k: r[k] for k in
            ("answer", "abstained", "citations", "tool_calls", "timings", "usage", "llm_mode")}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--json", help="also write the transcript to this file")
    a = ap.parse_args(argv)
    c = httpx.Client(base_url=a.base, timeout=120)
    H = lambda u: {"X-API-Key": f"demo-{u}"}  # noqa: E731
    out: dict = {"health": c.get("/health").json(), "scenes": []}
    print("health:", out["health"])

    for title, user, q in SCENES:
        r = c.post("/ask", json={"question": q}, headers=H(user)).json()
        out["scenes"].append(show(title, user, q, r))

    docs = {u: [d["title"] for d in c.get("/documents", headers=H(u)).json()["documents"]] for u in ("frank", "erin")}
    out["catalog"] = docs
    print(f"\n━━ Catalog is permission-filtered\n   frank sees {len(docs['frank'])} docs: {docs['frank']}\n   erin sees {len(docs['erin'])} docs")

    s = c.post("/search", json={"query": "who approves business class flights", "top_k": 3}, headers=H("alice")).json()
    out["search"] = s
    print("\n━━ Hybrid search internals (vector rank, keyword rank -> reranked score)")
    for x in s["results"]:
        print(f"   {x['score']:.3f}  ranks={ {k: v for k, v in x['ranks'].items() if k != 'fused_score'} }  {x['title']} › {x['section']}")

    # live ingest -> ACL change -> delete
    print("\n━━ Live upload + permission change (admin = erin)")
    life = []
    note = b"# Lab note\n\n## Result\n\nThe Orion prototype battery lasts 41 hours on a single charge."
    up = c.post("/ingest/file", files={"file": ("orion-lab-note.md", note, "text/markdown")},
                data={"allowed_groups": "engineering"}, headers=H("erin")).json()
    print(f"   uploaded: {up}")
    life.append({"step": "erin uploads orion-lab-note.md for group 'engineering'", "result": up})
    q = "How long does the Orion prototype battery last?"
    for step, user in [("engineer asks", "alice"), ("finance user asks", "bob")]:
        r = c.post("/ask", json={"question": q}, headers=H(user)).json()
        life.append(show(f"{step} ({user})", user, q, r))
    acl = c.patch(f"/documents/{up['document_id']}/acl", json={"allowed_groups": ["engineering", "finance"]}, headers=H("erin")).json()
    print(f"\n   ACL changed -> {acl['allowed_groups']}")
    life.append({"step": "erin grants 'finance' access", "result": acl})
    r = c.post("/ask", json={"question": q}, headers=H("bob")).json()
    life.append(show("finance user asks again (bob)", "bob", q, r))
    c.delete(f"/documents/{up['document_id']}", headers=H("erin"))
    life.append({"step": "erin deletes the document", "result": {"deleted": up["document_id"]}})
    out["lifecycle"] = life

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, default=str)
        print(f"\ntranscript written to {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

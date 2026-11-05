"""Tools the agent can call. Every tool receives the caller's groups from the
agent state - never from the LLM - so the model cannot widen its own access."""
from __future__ import annotations

from app.retrieval import Source, list_documents, search

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": (
                "Semantic + keyword search over internal documents: policies, handbooks, runbooks, "
                "reports, contracts, memos and ingested web pages (PDF/DOCX/HTML/Markdown). "
                "Use for any question answered by prose."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Focused search query; rephrase with key terms."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_structured_data",
            "description": (
                "Search tabular datasets (rows from CSV exports / database tables) such as monthly KPI "
                "metrics, office locations and headcount, compensation bands. Use for specific "
                "numbers by month, office, level, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Entity + metric, e.g. 'Lisbon office headcount'."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_documents",
            "description": "List documents in the catalog (title, type, version, date). Use for 'which documents...' questions.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Optional title/topic filter."}},
            },
        },
    },
]

TOOL_NAMES = {t["function"]["name"] for t in TOOL_SPECS}


def run_tool(name: str, args: dict, groups: list[str], mode: str, timings: dict) -> list[Source]:
    query = str(args.get("query") or "").strip()
    if name == "search_knowledge_base":
        return search(query, groups, table="chunks", mode=mode, timings=timings) if query else []
    if name == "search_structured_data":
        return search(query, groups, table="records", mode=mode, timings=timings) if query else []
    if name == "list_documents":
        docs = list_documents(groups, query or None, limit=15)
        n = len(docs)
        return [
            Source(
                kind="document", id=d["id"], document_id=d["id"], title=d["title"],
                source_uri=d["source_uri"], doc_type=d["doc_type"], version=d["version"],
                text=f"Document: {d['title']} (type: {d['doc_type']}, version {d['version']}, "
                     f"updated {d['updated_at'][:10] if d['updated_at'] else 'n/a'})"
                     + (f". {d['description']}" if d.get("description") else ""),
                score=1.0 - i / max(n, 1) * 0.5,
            )
            for i, d in enumerate(docs)
        ]
    raise ValueError(f"Unknown tool {name}")

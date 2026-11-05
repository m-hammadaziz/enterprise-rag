"""End-to-end tests against Postgres (offline embedding/rerank/LLM backends)."""
import pytest

from app import agent as agent_mod
from app import llm
from app.agent import ABSTAIN_MESSAGE, answer_question
from app.auth import get_user_groups
from app.config import settings
from app.retrieval import list_documents, search

pytestmark = pytest.mark.integration


def test_acl_enforced_in_retrieval(corpus):
    for mode in ("vector", "keyword", "hybrid", "hybrid_rerank"):
        hits = search("Project Atlas purchase price Brightline", ["all-staff", "engineering"], mode=mode, top_k=20)
        assert all("project-atlas" not in h.source_uri for h in hits), mode
    exec_hits = search("Project Atlas purchase price Brightline", ["exec"], top_k=3)
    assert exec_hits and "project-atlas" in exec_hits[0].source_uri


def test_no_groups_sees_nothing(corpus):
    assert search("annual leave", []) == []
    assert list_documents([]) == []


def test_catalog_is_permission_filtered(corpus):
    titles = {d["title"] for d in list_documents(["contractors"], limit=50)}
    assert "Information Security Policy" in titles
    assert "Board Memo: Project Atlas" not in titles and "Q3 2026 Financial Report" not in titles


def test_structured_search(corpus):
    hits = search("Lisbon office headcount", ["all-staff"], table="records", top_k=3)
    assert hits[0].kind == "record" and "headcount: 96" in hits[0].text


def test_agent_answers_with_valid_citations(corpus):
    r = answer_question("How many days of paid annual leave do full-time employees get?", get_user_groups("alice"))
    assert not r["abstained"]
    assert "25" in r["answer"]
    assert r["citations"] and all(c["title"] == "Corvane Employee Handbook 2026" for c in r["citations"])
    assert all(c["sid"] in {s["sid"] for s in r["retrieved"]} for c in r["citations"])


def test_agent_abstains_on_restricted_content(corpus):
    r = answer_question("What is the proposed purchase price for Project Atlas?", get_user_groups("alice"))
    assert r["abstained"] and r["answer"] == ABSTAIN_MESSAGE
    assert "38" not in r["answer"] and not r["citations"]
    assert all("project-atlas" not in s["source_uri"] for s in r["retrieved"])


def test_agent_abstains_when_nothing_relevant(corpus):
    r = answer_question("What is the Wi-Fi password for the Berlin office?", get_user_groups("alice"))
    assert r["abstained"]


def test_reingest_is_idempotent_and_acl_change_propagates(corpus):
    from app.db import get_pool
    from app.ingest.loaders import load_markdown
    from app.ingest.pipeline import ingest_loaded, set_document_acl

    def temp_hits(groups):  # vector search always returns neighbours, so filter to our doc
        return [h for h in search("zebra code", groups, top_k=20) if h.source_uri == "test://temp-acl.md"]

    doc = load_markdown("# Temp\n\n## Fact\n\nThe zebra code is 4711.", "Temp")
    r1 = ingest_loaded(doc, "test://temp-acl.md", ["hr"])
    try:
        assert ingest_loaded(doc, "test://temp-acl.md", ["hr"]).status == "unchanged"
        assert temp_hits(["hr"]) and not temp_hits(["engineering"])
        set_document_acl(r1.document_id, ["engineering"])
        assert temp_hits(["engineering"]) and not temp_hits(["hr"])
        doc2 = load_markdown("# Temp\n\n## Fact\n\nThe zebra code is 9999.", "Temp")
        r3 = ingest_loaded(doc2, "test://temp-acl.md", ["engineering"])
        assert r3.status == "updated" and r3.version == r1.version + 1
        assert "9999" in temp_hits(["engineering"])[0].text
    finally:
        with get_pool().connection() as conn:
            conn.execute("DELETE FROM documents WHERE source_uri='test://temp-acl.md'")


# ------------------------------------------------- LLM path (mocked model) ---
class FakeLLM:
    """Stands in for the OpenAI-compatible endpoint: plans with tool calls, then answers."""

    def __init__(self, answer: str):
        self.answer = answer
        self.calls = []

    def __call__(self, messages, temperature=0.0, tools=None, json_mode=False, max_tokens=800):
        self.calls.append({"tools": bool(tools), "messages": messages})
        u = llm.Usage(input_tokens=100, output_tokens=20, calls=1)
        if tools:
            return llm.ChatResult("", [{"name": "search_knowledge_base",
                                        "arguments": {"query": "annual leave days full-time"}}], u)
        return llm.ChatResult(self.answer, [], u)


@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setattr(settings, "groq_api_key", "test-key")

    def install(answer):
        fake = FakeLLM(answer)
        monkeypatch.setattr(agent_mod.llm, "chat", fake)
        return fake
    return install


def test_llm_path_strips_invalid_citations_and_tracks_cost(corpus, llm_on):
    fake = llm_on("Full-time employees get 25 days of annual leave [S1]. This is great [S99].")
    r = answer_question("How much annual leave do I get?", get_user_groups("alice"))
    assert not r["abstained"]
    assert "[S99]" not in r["answer"] and "[S1]" in r["answer"]
    assert [c["sid"] for c in r["citations"]] == ["S1"]
    assert r["usage"]["llm_calls"] == 2 and r["usage"]["cost_usd"] > 0
    # sources are passed as delimited data, and the planner got the tool specs
    assert fake.calls[0]["tools"] and "<source id=\"S1\"" in fake.calls[1]["messages"][1]["content"]


def test_llm_insufficient_evidence_leads_to_abstention(corpus, llm_on):
    llm_on("INSUFFICIENT_EVIDENCE")
    r = answer_question("How much annual leave do I get?", get_user_groups("alice"))
    assert r["abstained"] and r["rounds"] == settings.max_retrieval_rounds


def test_llm_answer_without_citations_is_rejected(corpus, llm_on):
    llm_on("You get 25 days.")
    r = answer_question("How much annual leave do I get?", get_user_groups("alice"))
    assert r["abstained"]


def test_planner_that_skips_documents_still_searches_them(corpus, monkeypatch):
    """Regression: gpt-oss picked only the table tool for 'Q3 revenue' and abstained."""
    monkeypatch.setattr(settings, "groq_api_key", "test-key")

    def fake(messages, temperature=0.0, tools=None, json_mode=False, max_tokens=800):
        u = llm.Usage(input_tokens=10, output_tokens=5, calls=1)
        if tools:
            return llm.ChatResult("", [{"name": "search_structured_data",
                                        "arguments": {"query": "total revenue Q3 2026"}}], u)
        return llm.ChatResult("Total revenue was 18.4 million USD in Q3 2026 [S1].", [], u)

    monkeypatch.setattr(agent_mod.llm, "chat", fake)
    r = answer_question("What was total revenue in Q3 2026?", get_user_groups("bob"))
    assert "search_knowledge_base" in [t["name"] for t in r["tool_calls"]]
    assert not r["abstained"] and r["citations"][0]["title"] == "Q3 2026 Financial Report"


def test_dashboard_is_served():
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as c:
        r = c.get("/")
    assert r.status_code == 200 and "Knowledge Agent" in r.text


def test_gpt_oss_style_citations_are_accepted(corpus, llm_on):
    """Regression: gpt-oss writes 【S1†L2-L4】; the answer used to be discarded."""
    llm_on("Full-time employees receive **25 days** of paid annual leave 【S1†L2-L4】.")
    r = answer_question("How many days of paid annual leave do full-time employees get?", get_user_groups("hammad"))
    assert not r["abstained"], r.get("rejected_draft")
    assert "[S1]" in r["answer"] and "【" not in r["answer"]
    assert r["citations"][0]["title"] == "Corvane Employee Handbook 2026"

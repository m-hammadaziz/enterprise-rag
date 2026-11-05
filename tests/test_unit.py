from pathlib import Path

import pytest

from app.ingest.chunker import chunk_blocks
from app.ingest.loaders import Block, load_bytes, load_markdown
from app.rerank import lexical_scores
from app.retrieval import rrf_fuse
from eval.metrics import evidence_in, fact_present, facts_score, percentile, retrieval_metrics

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


# ----------------------------------------------------------------- chunking --
def test_chunks_never_cross_sections():
    blocks = [Block("Leave", section="Leave", is_heading=True), Block("Annual leave is 25 days.", section="Leave"),
              Block("Sick", section="Sick", is_heading=True), Block("Sick leave is 12 days.", section="Sick")]
    chunks = chunk_blocks(blocks, target_words=100)
    assert [c.section for c in chunks] == ["Leave", "Sick"]
    assert "25 days" in chunks[0].text and "12 days" not in chunks[0].text
    assert chunks[0].text.startswith("Leave")  # heading kept as context


def test_long_section_is_split_with_overlap():
    para = " ".join(f"Sentence number {i} talks about policy item {i}." for i in range(60))
    chunks = chunk_blocks([Block(para, section="S")], target_words=60, overlap_words=10)
    assert len(chunks) > 3
    assert all(c.word_count <= 60 + 25 for c in chunks)
    # overlap: last sentence of chunk n appears at the start of chunk n+1
    last = chunks[0].text.split(". ")[-1].strip(".")
    assert last in chunks[1].text


def test_pdf_pages_are_citation_boundaries():
    blocks = [Block("a " * 20, page=1, section="X"), Block("b " * 20, page=2, section="X")]
    assert [c.page for c in chunk_blocks(blocks, target_words=500)] == [1, 2]


# ------------------------------------------------------------------ loaders --
@pytest.mark.parametrize("name,expected_title,needle", [
    ("docs/employee-handbook.pdf", "Corvane Employee Handbook 2026", "25 days of paid annual leave"),
    ("docs/travel-expense-policy.docx", "Travel and Expense Policy", "220 USD"),
    ("docs/deployment-guide.html", "Deployment Guide", "Flagpole"),
    ("docs/sales-playbook.md", "Sales Playbook", "MEDDIC"),
])
def test_loaders_extract_title_and_text(name, expected_title, needle):
    p = SAMPLE / name
    doc = load_bytes(p.read_bytes(), p.name)
    assert doc.title == expected_title
    assert needle in " ".join(b.text for b in doc.blocks)
    assert any(b.section for b in doc.blocks)


def test_html_strips_navigation_and_footer():
    p = SAMPLE / "docs/deployment-guide.html"
    text = " ".join(b.text for b in load_bytes(p.read_bytes(), p.name).blocks)
    assert "Intranet home" not in text and "internal use only" not in text


def test_docx_tables_become_key_value_text():
    p = SAMPLE / "docs/fy2027-budget-plan.docx"
    text = "\n".join(b.text for b in load_bytes(p.read_bytes(), p.name).blocks)
    assert "Department: Engineering; Budget (USD): 26.5 million; Planned new hires: 34" in text


def test_csv_rows():
    p = SAMPLE / "datasets/office-locations.csv"
    doc = load_bytes(p.read_bytes(), p.name)
    assert doc.doc_type == "csv" and len(doc.rows) == 6 and doc.rows[1]["city"] == "Lisbon"


def test_markdown_heading_path():
    doc = load_markdown("# T\n## A\ntext a\n### B\ntext b\n## C\ntext c", "x")
    secs = [b.section for b in doc.blocks if not b.is_heading]
    assert secs == ["T > A", "T > A > B", "T > C"]


def test_unsupported_format():
    with pytest.raises(ValueError):
        load_bytes(b"x", "file.exe")


# ---------------------------------------------------------------- retrieval --
def test_rrf_rewards_agreement():
    fused = rrf_fuse({"vector": [1, 2, 3], "keyword": [2, 4]}, k=60)
    assert fused[0][0] == 2                     # in both lists -> first
    assert fused[0][2] == {"vector": 2, "keyword": 1}
    assert {i for i, _, _ in fused} == {1, 2, 3, 4}


def test_lexical_reranker_prefers_relevant_passage():
    s = lexical_scores("how many sick days", ["Annual leave is 25 days.", "Employees get 12 paid sick days."])
    assert s[1] > s[0]


# ------------------------------------------------------------------ metrics --
@pytest.mark.parametrize("fact,text,ok", [
    ("25", "You get 25 days.", True),
    ("25", "You get 250 days.", False),
    ("25", "Rate is 1.25.", False),
    ("1500", "A budget of 1,500 USD.", True),
    ("5 percent|5%", "Canary gets 5% of traffic", True),
    ("vice president|vp", "Requires a VP.", True),
    ("18.4", "Revenue 18.45M", False),
])
def test_fact_matching(fact, text, ok):
    assert fact_present(fact, text) is ok


def test_facts_score_partial():
    assert facts_score(["25", "12"], "25 days annual") == 0.5


def test_evidence_tolerates_wrapping():
    assert evidence_in("receive 25 days of paid annual leave", "employees  receive 25\ndays of paid annual leave per year")


def test_retrieval_metrics():
    res = [{"text": "nothing", "source_uri": "a/x.md"}, {"text": "the cap is 220 USD", "source_uri": "a/travel.docx"}]
    m = retrieval_metrics(res, ["cap is 220 USD"], ["travel"])
    assert m["hit@1"] == 0 and m["hit@3"] == 1 and m["mrr@10"] == 0.5 and m["doc_hit@3"] == 1


def test_percentile():
    assert percentile([1, 2, 3, 4], 50) == 2.5 and percentile([], 95) == 0.0


# ------------------------------------------------- citation normalisation ---
from app.agent import normalize_citations  # noqa: E402


@pytest.mark.parametrize("raw,expected", [
    ("25 days 【S1】.", "25 days [S1]."),
    ("25 days [S1†L3-L5].", "25 days [S1]."),
    ("25 days 【S1†L3-L5】 and 12 sick days 【S2†L1】.", "25 days [S1] and 12 sick days [S2]."),
    ("25 days (S1).", "25 days [S1]."),
    ("25 days [Source 1].", "25 days [S1]."),
    ("25 days [S1; S3].", "25 days [S1, S3]."),
    ("25 days [S1][S2].", "25 days [S1][S2]."),
    ("25 days [1].", "25 days [S1]."),
    ("25 days [1, 2].", "25 days [S1, S2]."),
    ("In Q3 (2026) revenue grew.", "In Q3 (2026) revenue grew."),   # not a citation
    ("See [9].", "See [9]."),                                         # out of range -> untouched
    ("(see page 3)", "(see page 3)"),
    ("already fine [S2, S3]", "already fine [S2, S3]"),
])
def test_normalize_citations(raw, expected):
    assert normalize_citations(raw, n_sources=6) == expected

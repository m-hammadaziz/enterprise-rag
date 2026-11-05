import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client(corpus):
    with TestClient(app) as c:
        yield c


def h(user):
    return {"X-API-Key": f"demo-{user}"}


def test_health(client):
    r = client.get("/health").json()
    assert r["status"] == "ok" and r["pgvector"] and r["documents"] >= 18


def test_auth_required(client):
    assert client.post("/ask", json={"question": "annual leave?"}).status_code == 401
    assert client.post("/ask", json={"question": "annual leave?"}, headers={"X-API-Key": "nope"}).status_code == 401


def test_me(client):
    assert client.get("/me", headers=h("frank")).json()["groups"] == ["contractors"]


def test_ask_and_log(client):
    r = client.post("/ask", json={"question": "What is the hotel cap per night in standard cities?"}, headers=h("bob"))
    body = r.json()
    assert r.status_code == 200 and "220" in body["answer"] and body["citations"]


def test_search_and_documents_respect_acl(client):
    docs = client.get("/documents", headers=h("dave")).json()["documents"]
    titles = {d["title"] for d in docs}
    assert "Sales Playbook" in titles and "Q3 2026 Financial Report" not in titles
    res = client.post("/search", json={"query": "Q3 revenue", "top_k": 20}, headers=h("dave")).json()["results"]
    assert all("q3-2026" not in x["source_uri"] for x in res)


def test_ingest_requires_admin_and_works(client):
    files = {"file": ("note.md", io.BytesIO(b"# Lab note\n\n## Result\n\nThe flux capacitor needs 1.21 gigawatts."), "text/markdown")}
    assert client.post("/ingest/file", files=files, data={"allowed_groups": "engineering"}, headers=h("alice")).status_code == 403
    files = {"file": ("note.md", io.BytesIO(b"# Lab note\n\n## Result\n\nThe flux capacitor needs 1.21 gigawatts."), "text/markdown")}
    r = client.post("/ingest/file", files=files, data={"allowed_groups": "engineering"}, headers=h("erin"))
    assert r.status_code == 200, r.text
    doc_id = r.json()["document_id"]
    try:
        q = {"question": "How many gigawatts does the flux capacitor need?"}
        assert "1.21" in client.post("/ask", json=q, headers=h("alice")).json()["answer"]
        assert client.post("/ask", json=q, headers=h("bob")).json()["abstained"]
        assert client.patch(f"/documents/{doc_id}/acl", json={"allowed_groups": ["finance"]}, headers=h("erin")).status_code == 200
        assert not client.post("/ask", json=q, headers=h("bob")).json()["abstained"]
    finally:
        assert client.delete(f"/documents/{doc_id}", headers=h("erin")).status_code == 200


def test_ingest_rejects_empty_acl(client):
    files = {"file": ("x.md", io.BytesIO(b"# X\n\ntext here"), "text/markdown")}
    assert client.post("/ingest/file", files=files, data={"allowed_groups": " , "}, headers=h("erin")).status_code == 422


def test_url_ingest_blocks_internal_addresses(client):
    r = client.post("/ingest/url", json={"url": "http://127.0.0.1:5432/", "allowed_groups": ["all-staff"]}, headers=h("erin"))
    assert r.status_code == 422

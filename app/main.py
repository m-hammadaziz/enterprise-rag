from __future__ import annotations

from contextlib import asynccontextmanager
import json
import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from pathlib import Path

from fastapi.responses import FileResponse, JSONResponse
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.agent import answer_question
from app.auth import CurrentUser, admin_user, current_user, upsert_user
from app.config import settings
from app.db import close_pool, get_pool
from app.ingest.loaders import UnsupportedFormat
from app.ingest.pipeline import ingest_bytes, ingest_url, set_document_acl
from app.retrieval import MODES, list_documents, search

log = logging.getLogger("enterprise_rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_pool()  # applies db/init.sql (idempotent) and opens the pool
    # Load the embedding + reranker models now, so the first question isn't slow.
    log.warning("Loading embedding and reranker models (first start downloads them)...")
    try:
        from app.embeddings import embed_query
        from app.rerank import rerank_scores

        embed_query("warm up")
        rerank_scores("warm up", ["warm up"])
        log.warning("Models loaded - ready. Open http://localhost:8000")
    except Exception:  # never block startup on warm-up
        log.exception("model warm-up failed (will load on first request)")
    yield
    close_pool()


app = FastAPI(
    title="Enterprise Research Agent",
    description="Permission-aware hybrid RAG agent with citations and abstention.",
    version="1.0.0",
    lifespan=lifespan,
)


# ------------------------------------------------------------------ models ---
class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    mode: str = Field("hybrid_rerank", description=f"Retrieval mode: {', '.join(MODES)}")


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    source: str = Field("documents", pattern="^(documents|structured)$")
    mode: str = "hybrid_rerank"
    top_k: int = Field(8, ge=1, le=50)


class UrlIngestRequest(BaseModel):
    url: str
    allowed_groups: list[str]
    title: str | None = None


class AclRequest(BaseModel):
    allowed_groups: list[str]


class UserRequest(BaseModel):
    name: str
    groups: list[str]
    is_admin: bool = False


def _check_mode(mode: str) -> None:
    if mode not in MODES:
        raise HTTPException(422, f"mode must be one of {MODES}")


# --------------------------------------------------------------- endpoints ---
UI_FILE = Path(__file__).resolve().parent / "static" / "index.html"


@app.get("/", include_in_schema=False)
def ui():
    """Web dashboard (single HTML file, talks to the JSON API below)."""
    return FileResponse(UI_FILE)


@app.get("/health")
def health():
    with get_pool().connection() as conn:
        ext = conn.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'").fetchone()
        counts = conn.execute(
            "SELECT (SELECT count(*) FROM documents) AS documents, (SELECT count(*) FROM chunks) AS chunks, "
            "(SELECT count(*) FROM records) AS records"
        ).fetchone()
    return {
        "status": "ok", "pgvector": ext is not None, **counts,
        "llm_mode": "llm" if settings.llm_enabled else "extractive",
        "embed_backend": settings.embed_backend, "rerank_backend": settings.rerank_backend,
    }


@app.get("/me")
def me(user: CurrentUser = Depends(current_user)):
    return {"name": user.name, "groups": user.groups, "is_admin": user.is_admin}


@app.post("/ask")
def ask(req: AskRequest, user: CurrentUser = Depends(current_user)):
    _check_mode(req.mode)
    result = answer_question(req.question, user.groups, mode=req.mode)
    try:
        with get_pool().connection() as conn:
            conn.execute(
                """INSERT INTO query_logs (user_id, question, retrieved_ids, answer, latency_ms,
                   input_tokens, output_tokens, cost_usd, abstained, citations, timings)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (
                    user.id, req.question,
                    [r["id"] for r in result["retrieved"] if r["kind"] == "chunk"],
                    result["answer"], int(result["timings"]["total_ms"]),
                    result["usage"]["input_tokens"], result["usage"]["output_tokens"],
                    result["usage"]["cost_usd"], result["abstained"],
                    Jsonb(result["citations"]), Jsonb(result["timings"]),
                ),
            )
    except Exception:  # logging must never break answering
        log.exception("failed to write query log")
    return result


@app.post("/search")
def search_endpoint(req: SearchRequest, user: CurrentUser = Depends(current_user)):
    _check_mode(req.mode)
    timings: dict = {}
    table = "chunks" if req.source == "documents" else "records"
    hits = search(req.query, user.groups, table=table, mode=req.mode, top_k=req.top_k, timings=timings)
    return {"results": [h.citation() | {"ranks": h.ranks} for h in hits],
            "timings": {k: round(v, 1) for k, v in timings.items()}}


@app.get("/documents")
def documents(q: str | None = Query(None), limit: int = Query(50, le=200),
              user: CurrentUser = Depends(current_user)):
    return {"documents": list_documents(user.groups, q, limit)}


@app.post("/ingest/file")
async def ingest_file_endpoint(
    file: UploadFile = File(...),
    allowed_groups: str = Form(..., description="Comma-separated groups, e.g. 'engineering,all-staff'"),
    title: str | None = Form(None),
    metadata: str | None = Form(None, description="Optional JSON object"),
    admin: CurrentUser = Depends(admin_user),
):
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File larger than {settings.max_upload_mb} MB")
    try:
        meta = json.loads(metadata) if metadata else {}
        res = ingest_bytes(data, file.filename or "upload.txt", allowed_groups, title,
                           {**meta, "uploaded_by": admin.name})
    except (UnsupportedFormat, ValueError, json.JSONDecodeError) as e:
        raise HTTPException(422, str(e))
    return res.as_dict()


@app.post("/ingest/url")
def ingest_url_endpoint(req: UrlIngestRequest, admin: CurrentUser = Depends(admin_user)):
    if not settings.allow_url_ingest:
        raise HTTPException(403, "URL ingestion disabled")
    try:
        res = ingest_url(req.url, req.allowed_groups, req.title, {"uploaded_by": admin.name})
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(502, f"Could not fetch URL: {e}")
    return res.as_dict()


@app.patch("/documents/{document_id}/acl")
def update_acl(document_id: int, req: AclRequest, admin: CurrentUser = Depends(admin_user)):
    try:
        groups = set_document_acl(document_id, req.allowed_groups)
    except KeyError:
        raise HTTPException(404, "Document not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {"document_id": document_id, "allowed_groups": groups}


@app.delete("/documents/{document_id}")
def delete_document(document_id: int, admin: CurrentUser = Depends(admin_user)):
    with get_pool().connection() as conn:
        n = conn.execute("DELETE FROM documents WHERE id=%s", (document_id,)).rowcount
    if not n:
        raise HTTPException(404, "Document not found")
    return {"deleted": document_id}


@app.post("/admin/users")
def create_user(req: UserRequest, admin: CurrentUser = Depends(admin_user)):
    key = upsert_user(req.name, req.groups, req.is_admin)
    return JSONResponse({"name": req.name, "groups": sorted(set(req.groups)), "api_key": key}, status_code=201)

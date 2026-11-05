from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database -----------------------------------------------------------
    database_url: str = "postgresql://rag:rag@localhost:5432/rag"

    # --- LLM (any OpenAI-compatible endpoint: Groq, OpenAI, vLLM, Ollama...) ---
    # Leave GROQ_API_KEY empty to run in fully offline "extractive" mode
    # (no LLM calls; used by tests/CI and for cheap retrieval benchmarking).
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_s: float = 60.0
    # USD per 1M tokens, used for cost tracking in logs and the benchmark.
    llm_input_price_per_mtok: float = 0.59
    llm_output_price_per_mtok: float = 0.79

    # --- Embeddings -----------------------------------------------------------
    # "sentence-transformers" (real model, default) or "hash" (offline, no download)
    embed_backend: str = "sentence-transformers"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384  # must match chunks.embedding vector(N) in db/init.sql

    # --- Reranking ------------------------------------------------------------
    # "cross-encoder" (real model), "lexical" (offline) or "none"
    rerank_backend: str = "cross-encoder"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Retrieval ------------------------------------------------------------
    candidates_per_retriever: int = 30   # top-N from vector and from keyword search
    rrf_k: int = 60                      # Reciprocal Rank Fusion constant
    rerank_pool: int = 30                # fused candidates sent to the reranker
    final_top_k: int = 6                 # sources handed to the LLM
    hnsw_ef_search: int = 100

    # --- Evidence gate (abstention) --------------------------------------------
    # Minimum reranker score of the best source before we even try to answer.
    # Scores are normalised to 0..1 for every backend (sigmoid for cross-encoders).
    min_evidence_score_cross_encoder: float = 0.05
    min_evidence_score_lexical: float = 0.45
    min_evidence_score_none: float = 0.0
    max_retrieval_rounds: int = 2         # initial round + one query-rewrite retry

    # --- Chunking -------------------------------------------------------------
    chunk_target_words: int = 180
    chunk_overlap_words: int = 30

    # --- API ------------------------------------------------------------------
    max_upload_mb: int = 25
    allow_url_ingest: bool = True

    @property
    def llm_enabled(self) -> bool:
        return bool(self.groq_api_key.strip())

    @property
    def min_evidence_score(self) -> float:
        return {
            "cross-encoder": self.min_evidence_score_cross_encoder,
            "lexical": self.min_evidence_score_lexical,
        }.get(self.rerank_backend, self.min_evidence_score_none)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

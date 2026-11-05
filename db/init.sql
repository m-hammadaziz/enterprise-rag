-- Idempotent schema. Runs automatically on a fresh Docker volume
-- (docker-entrypoint-initdb.d) AND on every API/CLI start (app/db.py), so an
-- existing database is upgraded in place without losing data.

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------- identity --
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);
ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key_hash TEXT UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false;

CREATE TABLE IF NOT EXISTS user_groups (
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    group_name TEXT NOT NULL,
    PRIMARY KEY (user_id, group_name)
);

-- --------------------------------------------------------------- documents --
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    doc_type TEXT NOT NULL,              -- pdf | docx | html | md | txt | csv
    allowed_groups TEXT[] NOT NULL,
    version INT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
DO $$ BEGIN
    CREATE UNIQUE INDEX IF NOT EXISTS documents_source_uri_uq ON documents (source_uri);
EXCEPTION WHEN unique_violation THEN
    RAISE WARNING 'documents.source_uri has duplicates; dedupe them to enable versioned re-ingest';
END $$;
CREATE INDEX IF NOT EXISTS documents_acl_idx ON documents USING gin (allowed_groups);

-- ------------------------------------------------- unstructured: chunks --
CREATE TABLE IF NOT EXISTS chunks (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    page INT,
    section TEXT,
    allowed_groups TEXT[] NOT NULL,
    embedding vector(384),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS word_count INT;

CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_acl_idx ON chunks USING gin (allowed_groups);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (document_id);

-- ---------------------------------- structured: rows from CSV / DB tables --
CREATE TABLE IF NOT EXISTS records (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id) ON DELETE CASCADE,
    dataset TEXT NOT NULL,
    row_index INT NOT NULL,
    data JSONB NOT NULL,
    text_repr TEXT NOT NULL,
    allowed_groups TEXT[] NOT NULL,
    embedding vector(384),
    tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', text_repr)) STORED
);
CREATE INDEX IF NOT EXISTS records_embedding_idx ON records USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS records_tsv_idx ON records USING gin (tsv);
CREATE INDEX IF NOT EXISTS records_acl_idx ON records USING gin (allowed_groups);

-- --------------------------------------------------------------- telemetry --
CREATE TABLE IF NOT EXISTS query_logs (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    question TEXT,
    retrieved_ids INT[],
    answer TEXT,
    latency_ms INT,
    input_tokens INT,
    output_tokens INT,
    cost_usd NUMERIC(10,6),
    created_at TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS abstained BOOLEAN;
ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS citations JSONB;
ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS timings JSONB;

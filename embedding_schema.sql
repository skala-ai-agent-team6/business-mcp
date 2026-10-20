-- Apply after the product/order tables exist and pgvector is installed.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS product_embedding (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_id bigint REFERENCES product_model(id) ON DELETE CASCADE,
    part_id bigint REFERENCES part(id) ON DELETE CASCADE,
    content text NOT NULL,
    embedding vector(1536) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (model_id IS NOT NULL OR part_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS purchase_order_embedding (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purchase_order_id bigint NOT NULL UNIQUE
        REFERENCES purchase_order(id) ON DELETE CASCADE,
    content text NOT NULL,
    embedding vector(1536) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS product_embedding_vector_idx
    ON product_embedding USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS purchase_order_embedding_vector_idx
    ON purchase_order_embedding USING hnsw (embedding vector_cosine_ops);

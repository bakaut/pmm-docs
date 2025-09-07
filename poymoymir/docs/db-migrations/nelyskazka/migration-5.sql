-- 1. Подключаем расширение pgvector (если ещё не подключено)
-- 3. Эмбеддинг: вектор размерности text-embedding-3-small openai (1536)
CREATE EXTENSION IF NOT EXISTS vector;

BEGIN;

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS embedding vector(1536);

ALTER TABLE messages
    ADD COLUMN IF NOT EXISTS tg_msg_id INTEGER;

COMMIT;


DO \$\$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = 'messages_embedding_ivfflat_idx'
  ) THEN
    EXECUTE 'CREATE INDEX messages_embedding_ivfflat_idx ON messages USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)';
  END IF;
END
\$\$;

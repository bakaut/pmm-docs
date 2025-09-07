-- 1. Подключаем расширение pgvector (если ещё не подключено)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Таблица документов (вершин графа)
CREATE TABLE documents (
  id            SERIAL PRIMARY KEY,          -- уникальный идентификатор
  title         TEXT        NOT NULL,        -- заголовок или ключевое имя
  content       TEXT        NOT NULL,        -- полный текст до ~3000 символов
  summary       TEXT,                         -- предсгенеренный конспект
  created_at    TIMESTAMPTZ DEFAULT NOW()     -- время добавления
);

-- 3. Эмбеддинг: вектор размерности 1536 (или ваша)
ALTER TABLE documents
  ADD COLUMN embedding VECTOR(1536);

-- 4. Индекс для быстрого поиска по cosine-similarity
CREATE INDEX ON documents
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- 5. Таблица рёбер графа (связи между вершинами)
CREATE TABLE document_edges (
  id             SERIAL PRIMARY KEY,
  source_id      INTEGER NOT NULL
                   REFERENCES documents(id)
                   ON DELETE CASCADE,
  target_id      INTEGER NOT NULL
                   REFERENCES documents(id)
                   ON DELETE CASCADE,
  relation_type  TEXT,                       -- тип связи (например, "следующий", "ссылочный" и т.п.)
  UNIQUE(source_id, target_id, relation_type)
);

-- 6. (Опционально) История диалога: для хранения последних сообщений и их эмбеддингов
CREATE TABLE conversation_history (
  id            SERIAL PRIMARY KEY,
  user_text     TEXT        NOT NULL,
  role          TEXT        NOT NULL,       -- 'user' или 'assistant'
  embedding     VECTOR(1536),                -- эмбеддинг сообщения
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Индекс для истории, если планируете ретривал по embedding
CREATE INDEX ON conversation_history
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

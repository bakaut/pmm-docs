Коротко про «интервал после HWM», чтобы суммировать **только когда нужно**:

* **Держим счётчики от HWM**:
  `Δmsg` — новых сообщений, `Δtok` — оценка токенов, `Δt` — минут, `Δtopic` — дрейф темы (cosine).

* **Мини-интервалы (антидребезг, не суммировать раньше):**
  `MIN_MSGS_AFTER_HWM = 6–8`
  `MIN_TOKENS_AFTER_HWM = 600–800`
  `MIN_MINUTES_AFTER_HWM = 10–15`

* **Макс-интервалы (жёсткий запуск, суммировать сразу):**
  `MAX_MSGS_AFTER_HWM = 20–24`
  `MAX_TOKENS_AFTER_HWM = 2000–2500` (≈30% окна 8k)
  `MAX_MINUTES_AFTER_HWM = 120`
  `TOPIC_DRIFT_THRESHOLD = 0.6` (если выше — закрываем эпизод)

* **Правило запуска (гистерезис):**
  Суммировать, если выполнено **(любое из max)** **И** одновременно пройден **любой из min**.
  ИЛИ при `Δtopic ≥ 0.6` (смена темы) независимо от `Δt`.

* **Cooldown после свёртки:**
  `COOLDOWN_SECONDS = 60–120` + требование `≥ 3` новых сообщений после сводки, чтобы не пересворачивать.

* **Адаптация под стоимость/нагрузку:**
  При росте расходов или пиков — повышай `MIN_*`, `MAX_*` на 10–20%. При коротких репликах — поднимай `MAX_MSGS_AFTER_HWM` до 28–32.

* **Служебные события:**
  Инстант-сводка при: ручная команда `/summary`, «handoff» между агентами/сценами, крупный tool\_call (завершение задачи).

* **Идемпотентность/логика:**
  Считай `input_hash` окна `(HWM+1..cutoff)`; если уже суммировано — пропустить.
  В `summaries.trigger` фиксируй причину: `tokens|turns|time|topic_shift|manual`.

* **Обновление HWM:**
  Только после успешного `INSERT summaries` на диапазон `[from=HWM+1, to=cutoff]`.

Так ты избежишь «каждое N-ое сообщение» и будешь сворачивать **ровно тогда**, когда накопился смысловой объём или завершился эпизод.

-- Расширения
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- для gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector (если доступно)

-- Пользователи Telegram
CREATE TABLE users (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tg_user_id   BIGINT UNIQUE NOT NULL,
  username     TEXT,
  first_name   TEXT,
  last_name    TEXT,
  language_code TEXT,
  timezone     TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Сессии/диалоги
ALTER TABLE conversation_session (
  status                  TEXT DEFAULT 'active',       -- active|archived
  summary_hwm_msg_id      BIGINT NOT NULL DEFAULT 0,   -- High-Water Mark (последний покрытый msg)
  last_summary_at         TIMESTAMPTZ,
  msgs_since_summary      INTEGER NOT NULL DEFAULT 0,
  tokens_since_summary    INTEGER NOT NULL DEFAULT 0,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Сообщения (глобально монотонный id удобнее для HWM)
ALTER TABLE messages (
  content_hash     TEXT,                                -- sha256 hex (для идемпотентности/правок)
  token_count      INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  edited_at        TIMESTAMPTZ
);

-- Сводки эпизодов (summary-of-messages)
CREATE TABLE summaries (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    UUID NOT NULL REFERENCES conversations_session(id) ON DELETE CASCADE,
  from_msg_id        BIGINT NOT NULL,
  to_msg_id          BIGINT NOT NULL,
  summary_text       TEXT NOT NULL,
  trigger            TEXT NOT NULL,    -- tokens|turns|time|topic_shift|manual
  input_hash         TEXT NOT NULL,    -- sha256 окна (конкатенация id+content_hash)
  parent_summary_id  UUID REFERENCES summaries(id) ON DELETE SET NULL,
  status             TEXT NOT NULL DEFAULT 'completed', -- completed|superseded|dirty
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (from_msg_id <= to_msg_id)
);

-- Идемпотентность: не вставлять дубль по тому же окну/входу
CREATE UNIQUE INDEX ux_summaries_window_hash
  ON summaries(session_id, from_msg_id, to_msg_id, input_hash);

-- «Дальняя» память для RAG/фактов/сводок (векторный поиск)
CREATE TABLE memory_chunks (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID REFERENCES conversations(id) ON DELETE CASCADE,
  user_id          UUID REFERENCES users(id) ON DELETE CASCADE,
  source           TEXT NOT NULL,     -- chat|summarization|tool_output|profile
  content          TEXT NOT NULL,
  embedding        VECTOR(1536),      -- pgvector
  relevance        REAL DEFAULT 0,
  tags             TEXT[],
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- Индексы под типовые запросы
CREATE INDEX ix_messages_conv_id_id
  ON messages(session_id, id);                -- выборка окна [HWM+1..cutoff]
CREATE INDEX ix_messages_conv_created
  ON messages(session_id, created_at DESC);

CREATE INDEX ix_summaries_conv_to
  ON summaries(session_id, to_msg_id DESC);   -- быстрый доступ к последним сводкам

CREATE INDEX ix_memory_chunks_conv_created
  ON memory_chunks(session_id, created_at DESC);
CREATE INDEX ix_memory_chunks_tags_gin
  ON memory_chunks USING GIN(tags);

-- Индекс для векторного поиска (cosine). Подберите lists под объём.
CREATE INDEX ix_memory_chunks_embed_ivfflat
  ON memory_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);



Пояснения к полям/связям (кратко)

conversations_session.summary_hwm_msg_id — ваш HWM. Каждый INSERT summaries обновляет HWM до to_msg_id.

summaries (from_msg_id, to_msg_id, input_hash) + уникальный индекс — защита от повторной свёртки одного и того же окна.

messages.id BIGSERIAL — монотонный ключ для удобных диапазонов [HWM+1 .. cutoff].

memory_chunks.embedding — для RAG; можно класть как итоговые факты из сводок.

Мини-шаблоны запросов (для вашего пайплайна)

Выбрать только несуммированное окно:

SELECT *
FROM messages
WHERE session_id = :cid
  AND id > :hwm            -- conversations.summary_hwm_msg_id
  AND id <= :cutoff_id
ORDER BY id;


Вставить сводку и поднять HWM (в транзакции):

-- 1) INSERT INTO summaries (...) VALUES (...);
-- 2) UPDATE conversations
--    SET summary_hwm_msg_id = :cutoff_id,
--        last_summary_at = now(),
--        msgs_since_summary = 0,
--        tokens_since_summary = 0
--    WHERE id = :cid;

Коротко про Redis-модель (для полноты)

chat:{session_id}:recent — ZSET (score=timestamp), хранить последние 10–12 сообщений.

chat:{session_id}:lock:summarize — SETNX на 60–120 сек (антигонки).

chat:{session_id}:stats — HSET: msgs_since_summary, tokens_since_summary.

Если нужно — добавлю миграции, индексы под полнотекст/tri-gram и пример вычисления input_hash окна.


flowchart TD
  %% === High-level LLM summarization pipeline with HWM ===

  %% Ingestion
  A0([Start])
  A1[Receive message]
  A2[(DB: insert messages)]
  A3[(Redis: push recent window)]
  A4[Update counters since HWM: d_msg, d_tok, d_time]
  A0 --> A1 --> A2 --> A3 --> A4

  %% Trigger gate
  subgraph T[Trigger evaluation]
    direction TB
    Tmax{Max trigger? <br/>d_msg>=MAX_MSGS OR d_tok>=MAX_TOKENS OR d_time>=MAX_MIN OR topic_drift>=THR}
    Tmin{Min trigger? <br/>d_msg>=MIN_MSGS OR d_tok>=MIN_TOKENS OR d_time>=MIN_MIN}
    Tman{Manual or scheduled trigger?}
  end
  A4 --> Tmax --> Tmin --> Tman

  Tmax -- no --> C0[Skip summarize; normal reply] --> Z0([End])
  Tman -- no --> C0
  Tmax -- yes --> B0[Compute cutoff_id]
  Tman -- yes --> B0

  %% Window selection
  subgraph W[Select only non-summarized window]
    direction TB
    W1[HWM := conversations.summary_hwm_msg_id]
    W2[Window := messages with id > HWM and id <= cutoff_id]
    W3[Filter noise/system; collect evidence ids]
    W4[Compute input_hash over ids + content_hash]
  end
  B0 --> W1 --> W2 --> W3 --> W4

  %% Concurrency & idempotency
  L0{Acquire lock SETNX summarize:cid}
  W4 --> L0
  L0 -- no --> L1[Another worker running -> exit] --> Z0
  L0 -- yes --> D0{Duplicate window and hash?}

  D0 -- yes --> D1[Already summarized -> release lock] --> Z0
  D0 -- no --> S0[Build LLM input: recent msgs + window + last summaries + tool context]

  %% Summarization
  subgraph S[LLM summarization]
    direction TB
    S1[Call LLM Summarizer]
    S2{Valid JSON per schema?}
    S3[Retry with stricter prompt or smaller window]
    S4[If still invalid -> log error, release lock, exit]
  end
  S0 --> S1 --> S2
  S2 -- no --> S3 --> S2
  S2 -- no --> S4 --> Z0
  S2 -- yes --> P0[(DB: insert into summaries from=HWM+1..cutoff, trigger, input_hash)]

  %% Long-term memory
  M0{Extract facts from summary?}
  P0 --> M0
  M0 -- yes --> M1[(DB: upsert memory_chunks with embeddings and tags)]
  M0 -- no --> U0[(DB: update conversations set HWM=cutoff, reset counters)]
  M1 --> U0

  %% Cleanup
  R0[[Release lock; set cooldown; prune Redis window]]
  U0 --> R0 --> Z0

  %% Edit/dirty handling
  E0{Message edited or deleted inside summary range?}
  A2 --> E0
  E0 -- yes --> E1[(Mark affected summary as dirty)]
  E1 --> E2[Resummarize last segments -> new summary; old superseded]
  E2 --> U0



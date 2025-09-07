-- migrate-2.sql  (пример новой миграции)

BEGIN;

/* 1. Люди (как было, без изменений)
   users.id — ваш “человек”-владелец, у него может быть сколько угодно ботов.
*/

/* 2. Таблица ботов */
CREATE TABLE IF NOT EXISTS bots (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id   UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    username   TEXT,                -- @handle из BotFather (для наглядности)
    token      TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

/* 3. Сессии теперь знают, с каким ботом шёл диалог */
ALTER TABLE conversation_sessions
    ADD COLUMN IF NOT EXISTS bot_id UUID REFERENCES bots(id);

CREATE INDEX IF NOT EXISTS conversation_sessions_user_bot_idx
          ON conversation_sessions (user_id, bot_id)
       WHERE ended_at IS NULL;

ALTER TABLE bots
   ALTER COLUMN owner_id DROP NOT NULL;

ALTER TABLE bots
   ALTER COLUMN owner_id SET DEFAULT '00000000-0000-0000-0000-000000000000';

COMMIT;

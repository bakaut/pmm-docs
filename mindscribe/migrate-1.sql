-- migrate-1.sql - Migration to add summary table to existing database

BEGIN;

/* 
   Добавление таблицы summary к существующей схеме базы данных
   Эта миграция может быть выполнена на уже работающей базе данных
*/

-- Проверяем, что расширение uuid-ossp доступно (обычно уже установлено)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Создаем таблицу summary, если её ещё нет
-- Обновлено: без content колонки, со структурированными полями
CREATE TABLE IF NOT EXISTS public.summary (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    type        TEXT NOT NULL CHECK (type IN ('LALL', 'L1', 'L2', 'L3', 'L4')),
    
    -- Структурированные поля саммари
    summary_text TEXT,
    key_points   JSONB,
    main_themes  JSONB,
    insights     JSONB,
    language     TEXT DEFAULT 'ru',
    
    -- Дополнительные поля для отслеживания
    group_id     TEXT,
    source_range TEXT,
    message_count INTEGER,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Создаем индексы, если их ещё нет
CREATE INDEX IF NOT EXISTS summary_session_id_idx ON public.summary (session_id);
CREATE INDEX IF NOT EXISTS summary_user_id_idx ON public.summary (user_id);
CREATE INDEX IF NOT EXISTS summary_type_idx ON public.summary (type);
CREATE INDEX IF NOT EXISTS summary_created_at_idx ON public.summary (created_at);
CREATE INDEX IF NOT EXISTS summary_session_type_idx ON public.summary (session_id, type);
CREATE INDEX IF NOT EXISTS summary_session_user_type_idx ON public.summary (session_id, user_id, type);

-- Индексы для структурированных полей
CREATE INDEX IF NOT EXISTS summary_summary_text_idx ON public.summary USING gin(to_tsvector('russian', summary_text));
CREATE INDEX IF NOT EXISTS summary_key_points_idx ON public.summary USING gin(key_points);
CREATE INDEX IF NOT EXISTS summary_main_themes_idx ON public.summary USING gin(main_themes);
CREATE INDEX IF NOT EXISTS summary_insights_idx ON public.summary USING gin(insights);
CREATE INDEX IF NOT EXISTS summary_language_idx ON public.summary (language);
CREATE INDEX IF NOT EXISTS summary_group_id_idx ON public.summary (group_id);
CREATE INDEX IF NOT EXISTS summary_source_range_idx ON public.summary (source_range);
CREATE INDEX IF NOT EXISTS summary_processed_at_idx ON public.summary (processed_at);


-- Добавляем комментарии
COMMENT ON TABLE public.summary IS 'Таблица для хранения суммаризированного контента с различными уровнями агрегации (структурированное хранение)';
COMMENT ON COLUMN public.summary.type IS 'Тип саммари: LALL (все сообщения), L1 (15 сообщений), L2 (4x15 сообщений), L3 (4x4x15 сообщений), L4 (4x4x4x15 сообщений)';
COMMENT ON COLUMN public.summary.summary_text IS 'Краткое саммари основного содержания';
COMMENT ON COLUMN public.summary.key_points IS 'Ключевые точки в виде JSON массива строк';
COMMENT ON COLUMN public.summary.main_themes IS 'Основные темы в виде JSON массива строк';
COMMENT ON COLUMN public.summary.insights IS 'Важные наблюдения в виде JSON массива строк';
COMMENT ON COLUMN public.summary.language IS 'Язык контента (ru, en, etc.)';
COMMENT ON COLUMN public.summary.group_id IS 'Идентификатор группы для отслеживания иерархии (L1_0, L2_1, etc.)';
COMMENT ON COLUMN public.summary.source_range IS 'Диапазон исходных данных (message_1_15, l1_0_3, etc.)';
COMMENT ON COLUMN public.summary.message_count IS 'Количество исходных сообщений в группе';
COMMENT ON COLUMN public.summary.processed_at IS 'Время обработки саммари';

COMMIT;

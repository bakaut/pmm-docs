-- init.sql - Initial migration for MindScribe summary functionality

BEGIN;

/* 
   Таблица summary для хранения суммаризированного контента
   Согласно комментарию в flow/index.py:
   - LALL - все сообщения
   - L1 15m - 15 сообщений
   - L2 4L1 - 4 раза по 15 сообщений
   - L3 4L2 - 4 раза по 4 раза по 15 сообщений
   - L4 4L3 - 4 раза по 4 раза по 4 раза по 15 сообщений
*/

CREATE TABLE IF NOT EXISTS public.summary (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id  TEXT NOT NULL,                          -- Идентификатор сессии
    user_id     TEXT NOT NULL,                          -- Идентификатор пользователя
    role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')), -- Роль автора
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),     -- Время создания
    type        TEXT NOT NULL CHECK (type IN ('LALL', 'L1', 'L2', 'L3', 'L4')), -- Тип саммари
    
    -- Структурированные поля саммари (migrate-3.sql)
    summary_text TEXT,                                   -- Краткое саммари основного содержания
    key_points   JSONB,                                  -- Ключевые точки в виде массива
    main_themes  JSONB,                                  -- Основные темы в виде массива  
    insights     JSONB,                                  -- Важные наблюдения в виде массива
    language     TEXT DEFAULT 'ru',                     -- Язык контента
    
    -- Дополнительные поля для отслеживания (migrate-2.sql)
    group_id     TEXT,                                   -- Идентификатор группы
    source_range TEXT,                                   -- Диапазон исходных данных
    message_count INTEGER,                               -- Количество сообщений в группе
    processed_at TIMESTAMPTZ DEFAULT NOW()              -- Время обработки
);

-- Индексы для оптимизации запросов
CREATE INDEX IF NOT EXISTS summary_session_id_idx ON public.summary (session_id);
CREATE INDEX IF NOT EXISTS summary_user_id_idx ON public.summary (user_id);
CREATE INDEX IF NOT EXISTS summary_type_idx ON public.summary (type);
CREATE INDEX IF NOT EXISTS summary_created_at_idx ON public.summary (created_at);
CREATE INDEX IF NOT EXISTS summary_session_type_idx ON public.summary (session_id, type);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS summary_session_user_type_idx ON public.summary (session_id, user_id, type);

-- Создаем индексы для структурированных полей
CREATE INDEX IF NOT EXISTS summary_summary_text_idx ON public.summary USING gin(to_tsvector('russian', summary_text));
CREATE INDEX IF NOT EXISTS summary_key_points_idx ON public.summary USING gin(key_points);
CREATE INDEX IF NOT EXISTS summary_main_themes_idx ON public.summary USING gin(main_themes);
CREATE INDEX IF NOT EXISTS summary_insights_idx ON public.summary USING gin(insights);
CREATE INDEX IF NOT EXISTS summary_language_idx ON public.summary (language);
CREATE INDEX IF NOT EXISTS summary_group_id_idx ON public.summary (group_id);
CREATE INDEX IF NOT EXISTS summary_source_range_idx ON public.summary (source_range);
CREATE INDEX IF NOT EXISTS summary_processed_at_idx ON public.summary (processed_at);

-- Комментарии для документации
COMMENT ON TABLE public.summary IS 'Таблица для хранения суммаризированного контента с различными уровнями агрегации (структурированное хранение)';
COMMENT ON COLUMN public.summary.type IS 'Тип саммари: LALL (все сообщения), L1 (15 сообщений), L2 (4x15 сообщений), L3 (4x4x15 сообщений), L4 (4x4x4x15 сообщений)';
COMMENT ON COLUMN public.summary.session_id IS 'Идентификатор сессии для группировки связанных саммари';
COMMENT ON COLUMN public.summary.user_id IS 'Идентификатор пользователя';
COMMENT ON COLUMN public.summary.role IS 'Роль автора сообщения: user, assistant, system';
COMMENT ON COLUMN public.summary.summary_text IS 'Краткое саммари основного содержания';
COMMENT ON COLUMN public.summary.key_points IS 'Ключевые точки в виде JSON массива строк';
COMMENT ON COLUMN public.summary.main_themes IS 'Основные темы в виде JSON массива строк';
COMMENT ON COLUMN public.summary.insights IS 'Важные наблюдения в виде JSON массива строк';
COMMENT ON COLUMN public.summary.language IS 'Язык контента (ru, en, etc.)';
COMMENT ON COLUMN public.summary.group_id IS 'Идентификатор группы для отслеживания иерархии (L1_0, L2_1, etc.)';
COMMENT ON COLUMN public.summary.source_range IS 'Диапазон исходных данных (message_1_15, l1_0_3, etc.)';
COMMENT ON COLUMN public.summary.message_count IS 'Количество исходных сообщений в группе';
COMMENT ON COLUMN public.summary.processed_at IS 'Время обработки саммари';

-- Создаем таблицу для отслеживания состояния обработки сессий (migrate-2.sql)
CREATE TABLE IF NOT EXISTS public.summary_processing_state (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT NOT NULL,
    summary_type    TEXT NOT NULL CHECK (summary_type IN ('LALL', 'L1', 'L2', 'L3', 'L4')),
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    last_processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_message_count INTEGER NOT NULL DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'pending' CHECK (processing_status IN ('pending', 'processing', 'completed', 'error')),
    
    UNIQUE(session_id, summary_type, role)
);

-- Индексы для таблицы состояний обработки
CREATE INDEX IF NOT EXISTS summary_processing_state_session_idx ON public.summary_processing_state (session_id);
CREATE INDEX IF NOT EXISTS summary_processing_state_type_idx ON public.summary_processing_state (summary_type);
CREATE INDEX IF NOT EXISTS summary_processing_state_status_idx ON public.summary_processing_state (processing_status);

-- Комментарии для таблицы состояний
COMMENT ON TABLE public.summary_processing_state IS 'Таблица для отслеживания состояния обработки саммари по сессиям';
COMMENT ON COLUMN public.summary_processing_state.processing_status IS 'Статус обработки: pending, processing, completed, error';

COMMIT;

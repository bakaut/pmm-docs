-- migrate-2.sql - Add processing state tracking to summary table

BEGIN;

-- Добавляем новые поля для отслеживания состояния обработки
ALTER TABLE public.summary 
ADD COLUMN IF NOT EXISTS group_id TEXT,           -- Идентификатор группы (L1_0, L2_1, etc.)
ADD COLUMN IF NOT EXISTS source_range TEXT,       -- Диапазон исходных данных (message_1_15, l1_0_3, etc.)
ADD COLUMN IF NOT EXISTS message_count INTEGER,   -- Количество сообщений в группе
ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ DEFAULT NOW(); -- Время обработки

-- Добавляем таблицу для отслеживания состояния обработки сессий
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

-- Создаем индексы для новых полей
CREATE INDEX IF NOT EXISTS summary_group_id_idx ON public.summary (group_id);
CREATE INDEX IF NOT EXISTS summary_source_range_idx ON public.summary (source_range);
CREATE INDEX IF NOT EXISTS summary_processed_at_idx ON public.summary (processed_at);

CREATE INDEX IF NOT EXISTS summary_processing_state_session_idx ON public.summary_processing_state (session_id);
CREATE INDEX IF NOT EXISTS summary_processing_state_type_idx ON public.summary_processing_state (summary_type);
CREATE INDEX IF NOT EXISTS summary_processing_state_status_idx ON public.summary_processing_state (processing_status);

-- Комментарии для новых полей
COMMENT ON COLUMN public.summary.group_id IS 'Идентификатор группы для отслеживания иерархии (L1_0, L2_1, etc.)';
COMMENT ON COLUMN public.summary.source_range IS 'Диапазон исходных данных (message_1_15, l1_0_3, etc.)';
COMMENT ON COLUMN public.summary.message_count IS 'Количество исходных сообщений в группе';
COMMENT ON COLUMN public.summary.processed_at IS 'Время обработки саммари';

COMMENT ON TABLE public.summary_processing_state IS 'Таблица для отслеживания состояния обработки саммари по сессиям';
COMMENT ON COLUMN public.summary_processing_state.processing_status IS 'Статус обработки: pending, processing, completed, error';

COMMIT;

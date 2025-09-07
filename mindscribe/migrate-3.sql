-- migrate-3.sql - Migrate from JSON content to separate fields for summary components

BEGIN;

-- Добавляем новые колонки для отдельных полей саммари
ALTER TABLE public.summary 
ADD COLUMN IF NOT EXISTS summary_text TEXT,           -- Краткое саммари основного содержания
ADD COLUMN IF NOT EXISTS key_points JSONB,           -- Ключевые точки в виде массива
ADD COLUMN IF NOT EXISTS main_themes JSONB,          -- Основные темы в виде массива  
ADD COLUMN IF NOT EXISTS insights JSONB,             -- Важные наблюдения в виде массива
ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'ru'; -- Язык контента

-- Миграция существующих данных из JSON поля content в отдельные поля
-- Обновляем записи, где content содержит валидный JSON
UPDATE public.summary 
SET 
    summary_text = COALESCE(
        (content::jsonb ->> 'summary'), 
        content  -- fallback к оригинальному content если это не JSON
    ),
    key_points = CASE 
        WHEN content::text ~ '^{.*}$' THEN (content::jsonb -> 'key_points')
        ELSE '[]'::jsonb
    END,
    main_themes = CASE 
        WHEN content::text ~ '^{.*}$' THEN (content::jsonb -> 'main_themes')
        ELSE '[]'::jsonb
    END,
    insights = CASE 
        WHEN content::text ~ '^{.*}$' THEN (content::jsonb -> 'insights')
        ELSE '[]'::jsonb
    END,
    language = CASE 
        WHEN content::text ~ '^{.*}$' THEN COALESCE((content::jsonb ->> 'language'), 'ru')
        ELSE 'ru'
    END
WHERE summary_text IS NULL;

-- Создаем индексы для новых полей
CREATE INDEX IF NOT EXISTS summary_summary_text_idx ON public.summary USING gin(to_tsvector('russian', summary_text));
CREATE INDEX IF NOT EXISTS summary_key_points_idx ON public.summary USING gin(key_points);
CREATE INDEX IF NOT EXISTS summary_main_themes_idx ON public.summary USING gin(main_themes);
CREATE INDEX IF NOT EXISTS summary_insights_idx ON public.summary USING gin(insights);
CREATE INDEX IF NOT EXISTS summary_language_idx ON public.summary (language);

-- Добавляем комментарии для новых полей
COMMENT ON COLUMN public.summary.summary_text IS 'Краткое саммари основного содержания';
COMMENT ON COLUMN public.summary.key_points IS 'Ключевые точки в виде JSON массива строк';
COMMENT ON COLUMN public.summary.main_themes IS 'Основные темы в виде JSON массива строк';
COMMENT ON COLUMN public.summary.insights IS 'Важные наблюдения в виде JSON массива строк';
COMMENT ON COLUMN public.summary.language IS 'Язык контента (ru, en, etc.)';

-- После успешной миграции, поле content можно оставить для обратной совместимости
-- или удалить в следующей миграции после тестирования
-- ALTER TABLE public.summary DROP COLUMN IF EXISTS content;

COMMIT;

-- migrate-4.sql - Remove redundant content column from summary table

BEGIN;

-- The content column is now redundant since migrate-3.sql introduced separate fields
-- for summary components. This migration removes the content column to clean up the schema.

-- First, ensure all data has been migrated to the new structured fields
-- (This should have been done in migrate-3.sql, but we double-check)
UPDATE public.summary 
SET 
    summary_text = COALESCE(summary_text, 
        CASE 
            WHEN content::text ~ '^{.*}$' THEN (content::jsonb ->> 'summary')
            ELSE content
        END
    ),
    key_points = COALESCE(key_points,
        CASE 
            WHEN content::text ~ '^{.*}$' THEN (content::jsonb -> 'key_points')
            ELSE '[]'::jsonb
        END
    ),
    main_themes = COALESCE(main_themes,
        CASE 
            WHEN content::text ~ '^{.*}$' THEN (content::jsonb -> 'main_themes')
            ELSE '[]'::jsonb
        END
    ),
    insights = COALESCE(insights,
        CASE 
            WHEN content::text ~ '^{.*}$' THEN (content::jsonb -> 'insights')
            ELSE '[]'::jsonb
        END
    ),
    language = COALESCE(language,
        CASE 
            WHEN content::text ~ '^{.*}$' THEN COALESCE((content::jsonb ->> 'language'), 'ru')
            ELSE 'ru'
        END
    )
WHERE summary_text IS NULL OR key_points IS NULL OR main_themes IS NULL OR insights IS NULL;

-- Remove the redundant content column
ALTER TABLE public.summary DROP COLUMN IF EXISTS content;

-- Update comment for the table to reflect the change
COMMENT ON TABLE public.summary IS 'Таблица для хранения суммаризированного контента с различными уровнями агрегации (структурированное хранение)';

COMMIT;

BEGIN;
create table if not exists public.songs (
    id         uuid primary key default uuid_generate_v4(),
    user_id    uuid references public.users(id) on delete cascade,
    title      text,
    prompt     text,
    style      text,
    task_id    text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
COMMIT;

BEGIN;
ALTER TABLE songs
    ADD COLUMN IF NOT EXISTS session_id uuid references conversation_sessions(id) on delete cascade;
COMMIT;

BEGIN;
ALTER TABLE public.messages ADD COLUMN IF NOT EXISTS analysis JSONB;
COMMIT;

BEGIN;
ALTER TABLE public.songs ADD COLUMN IF NOT EXISTS path text;
COMMIT;

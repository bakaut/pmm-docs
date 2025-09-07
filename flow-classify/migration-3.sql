BEGIN;
create table if not exists public.tg_users (
    id             BIGINT  primary key default 0,
    user_id        uuid references public.users(id) on delete cascade,
    warnings       INTEGER     NOT NULL DEFAULT 0,
    blocked        BOOLEAN     NOT NULL DEFAULT FALSE,
    blocked_reason TEXT        NOT NULL DEFAULT '',
    blocked_at timestamptz default now()
);
COMMIT;

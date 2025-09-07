-- ─────────────────────────────────────
--  Расширения
-- ─────────────────────────────────────
create extension if not exists "uuid-ossp";
create extension if not exists "pgcrypto";

-- ─────────────────────────────────────
--  Типы и ENUM
-- ─────────────────────────────────────
do $$
begin
  if not exists (select 1 from pg_type where typname = 'role') then
     create type role as enum ('user', 'assistant');
  end if;
end$$;

-- ─────────────────────────────────────
--  Таблица users
-- ─────────────────────────────────────
create table if not exists public.users (
    id         uuid primary key default uuid_generate_v4(),
    chat_id    bigint  not null unique,
    full_name  text,
    created_at timestamptz default now()
);

-- ─────────────────────────────────────
--  Таблица conversation_sessions
-- ─────────────────────────────────────
create table if not exists public.conversation_sessions (
    id          uuid primary key default uuid_generate_v4(),
    user_id     uuid references public.users(id) on delete cascade,
    started_at  timestamptz not null default now(),
    ended_at    timestamptz,
    model       text        not null,
    constraint chk_ended_at check (ended_at is null or ended_at >= started_at)
);

create index if not exists convo_user_idx
  on public.conversation_sessions(user_id, started_at desc);

-- ─────────────────────────────────────
--  Таблица messages
-- ─────────────────────────────────────
create table if not exists public.messages (
    id          uuid primary key default uuid_generate_v4(),
    session_id  uuid references public.conversation_sessions(id) on delete cascade,
    user_id     uuid references public.users(id) on delete cascade,
    role        role not null,
    content     text not null,
    analysis jsonb,
    created_at  timestamptz default now()
);

create index if not exists msg_session_created_idx
  on public.messages(session_id, created_at);

-- ─────────────────────────────────────
--  Политики RLS (Supabase)
-- ─────────────────────────────────────
alter table public.users                enable row level security;
alter table public.conversation_sessions enable row level security;
alter table public.messages             enable row level security;

--  Разрешаем пользователю (анонимному ключу) видеть только свои строки
create policy "Users: self" on public.users
  for all using (auth.uid()::text = id::text);

create policy "Sessions: owner" on public.conversation_sessions
  for all using (auth.uid()::text = user_id::text);

create policy "Messages: owner" on public.messages
  for all using (auth.uid()::text = user_id::text);

create policy "Songs: owner" on public.songs
  for all using (auth.uid()::text = user_id::text);

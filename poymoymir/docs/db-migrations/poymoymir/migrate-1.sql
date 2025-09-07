---------------------------------------------------------------
--  Allow anon to insert into users / sessions / messages
---------------------------------------------------------------

alter table public.users
  enable row level security;

create policy "Users: anon insert"
  on public.users
  for insert
  with check (true);  -- или запретите менять id/created_at по своему вкусу

create policy "Sessions: anon insert"
  on public.conversation_sessions
  for insert
  with check (true);

create policy "Messages: anon insert"
  on public.messages
  for insert
  with check (true);

create table sessions (
  session_id text primary key,
  start_ts bigint not null
);
create table payments (
  order_id text primary key,
  session_id text references sessions(session_id),
  status boolean not null default false
);

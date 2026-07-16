-- Server-side login session table for limiting one account to two active devices.
-- Run this in Supabase Dashboard > SQL Editor before enforcing the device limit in production.

create table if not exists public.user_login_sessions (
  session_id text primary key,
  user_id bigint not null references public.users(id) on delete cascade,
  username text not null default '',
  ip_address text not null default '',
  user_agent text not null default '',
  is_active boolean not null default true,
  created_at timestamptz not null,
  last_seen_at timestamptz not null,
  revoked_at timestamptz,
  revoked_reason text not null default ''
);

create index if not exists user_login_sessions_active_idx
on public.user_login_sessions (user_id, is_active, created_at desc);

alter table public.user_login_sessions enable row level security;

grant select, insert, update, delete on public.user_login_sessions to service_role;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'user_login_sessions'
      and policyname = 'backend service can manage user login sessions'
  ) then
    create policy "backend service can manage user login sessions"
    on public.user_login_sessions
    for all
    to service_role
    using (true)
    with check (true);
  end if;
end $$;

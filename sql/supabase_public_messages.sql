create table if not exists public.public_message_sender_rules (
  id bigserial primary key,
  source_type text not null check (source_type in ('email', 'sms')),
  sender_pattern text not null,
  label text not null default '',
  is_active boolean not null default true,
  created_by text not null default '',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists public_message_sender_rules_unique_idx
on public.public_message_sender_rules (source_type, lower(sender_pattern));

create index if not exists public_message_sender_rules_active_idx
on public.public_message_sender_rules (source_type, is_active, sender_pattern);

alter table public.public_message_sender_rules enable row level security;

revoke all on table public.public_message_sender_rules from anon, authenticated;
grant select, insert, update, delete on table public.public_message_sender_rules to service_role;
grant usage, select on sequence public.public_message_sender_rules_id_seq to service_role;

insert into public.features (code, name, parent_code, sort_order)
values
  ('publicmessages', U&'N\1ED9i dung public', 'baocaomoi', 39),
  ('public_messages.view', U&'Xem n\1ED9i dung public', 'publicmessages', 391),
  ('public_messages.manage', U&'Qu\1EA3n tr\1ECB n\1ED9i dung public', 'publicmessages', 392)
on conflict (code) do nothing;

insert into public.user_permissions (user_id, feature_code)
select users.id, features.code
from public.users
cross join public.features
where users.role = 'admin'
  and features.code in ('publicmessages', 'public_messages.view', 'public_messages.manage')
on conflict do nothing;

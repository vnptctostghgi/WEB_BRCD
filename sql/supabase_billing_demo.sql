-- Demo billing/subscription tables for VNPTCTO.COM.
-- Run this in Supabase Dashboard > SQL Editor before using billing controls in production.

create table if not exists public.billing_plans (
  code text primary key,
  name text not null,
  paid_months integer not null,
  bonus_months integer not null default 0,
  price_vnd bigint not null default 0,
  is_active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

insert into public.billing_plans (code, name, paid_months, bonus_months, price_vnd, is_active, sort_order, created_at, updated_at)
values
  ('monthly', '1 thang', 1, 0, 99000, true, 10, now(), now()),
  ('quarterly', '3 thang', 3, 0, 279000, true, 20, now(), now()),
  ('six_months', '6 thang tang 1', 6, 1, 539000, true, 30, now(), now()),
  ('yearly', '12 thang tang 2', 12, 2, 999000, true, 40, now(), now())
on conflict (code) do nothing;

create table if not exists public.user_billing (
  user_id bigint primary key references public.users(id) on delete cascade,
  billing_enabled boolean not null default false,
  plan_code text not null default 'monthly' references public.billing_plans(code),
  started_at timestamptz,
  expires_at timestamptz,
  status text not null default 'disabled',
  last_invoice_id text not null default '',
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create index if not exists user_billing_status_idx
on public.user_billing (billing_enabled, status, expires_at);

create table if not exists public.billing_invoices (
  invoice_id text primary key,
  user_id bigint not null references public.users(id) on delete cascade,
  plan_code text not null references public.billing_plans(code),
  amount_vnd bigint not null default 0,
  status text not null default 'pending',
  payment_code text not null unique,
  qr_payload text not null default '',
  created_at timestamptz not null,
  due_at timestamptz not null,
  paid_at timestamptz,
  updated_at timestamptz not null
);

create index if not exists billing_invoices_user_idx
on public.billing_invoices (user_id, created_at desc);

create table if not exists public.billing_payments (
  payment_id text primary key,
  invoice_id text not null references public.billing_invoices(invoice_id) on delete cascade,
  user_id bigint not null references public.users(id) on delete cascade,
  provider text not null default 'demo_vietqr',
  transaction_ref text not null default '',
  amount_vnd bigint not null default 0,
  raw_payload_json jsonb not null default '{}'::jsonb,
  paid_at timestamptz not null,
  created_at timestamptz not null
);

create index if not exists billing_payments_invoice_idx
on public.billing_payments (invoice_id);

alter table public.billing_plans enable row level security;
alter table public.user_billing enable row level security;
alter table public.billing_invoices enable row level security;
alter table public.billing_payments enable row level security;

grant select, insert, update, delete on public.billing_plans to service_role;
grant select, insert, update, delete on public.user_billing to service_role;
grant select, insert, update, delete on public.billing_invoices to service_role;
grant select, insert, update, delete on public.billing_payments to service_role;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'billing_plans'
      and policyname = 'backend service can manage billing plans'
  ) then
    create policy "backend service can manage billing plans"
    on public.billing_plans
    for all
    to service_role
    using (true)
    with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'user_billing'
      and policyname = 'backend service can manage user billing'
  ) then
    create policy "backend service can manage user billing"
    on public.user_billing
    for all
    to service_role
    using (true)
    with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'billing_invoices'
      and policyname = 'backend service can manage billing invoices'
  ) then
    create policy "backend service can manage billing invoices"
    on public.billing_invoices
    for all
    to service_role
    using (true)
    with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'billing_payments'
      and policyname = 'backend service can manage billing payments'
  ) then
    create policy "backend service can manage billing payments"
    on public.billing_payments
    for all
    to service_role
    using (true)
    with check (true);
  end if;
end $$;

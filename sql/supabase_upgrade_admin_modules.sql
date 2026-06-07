-- Chay file nay trong Supabase Dashboard > SQL Editor
-- Muc dich: bo sung cot nhan vien, phan vung du lieu va quyen du lieu.

alter table public.users add column if not exists employee_code text;
alter table public.users add column if not exists email text;
alter table public.users add column if not exists phone text;
alter table public.users add column if not exists birth_date date;
alter table public.users add column if not exists gender text;
alter table public.users add column if not exists department text;
alter table public.users add column if not exists job_title text;

create unique index if not exists users_employee_code_lower_idx
on public.users (lower(employee_code))
where employee_code is not null;

create unique index if not exists users_email_lower_idx
on public.users (lower(email))
where email is not null;

create table if not exists public.data_regions (
  code text primary key,
  name text not null,
  is_active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.user_data_permissions (
  user_id bigint not null references public.users(id) on delete cascade,
  region_code text not null references public.data_regions(code) on delete cascade,
  primary key (user_id, region_code)
);

insert into public.data_regions (code, name, is_active, sort_order, created_at, updated_at)
values
  ('ALL', 'Tat ca', true, 0, now(), now()),
  ('13', 'Can Tho', true, 10, now(), now()),
  ('66', 'Hau Giang', true, 20, now(), now()),
  ('47', 'Soc Trang', true, 30, now(), now())
on conflict (code) do update
set name = excluded.name,
    is_active = excluded.is_active,
    sort_order = excluded.sort_order,
    updated_at = now();

alter table public.data_regions enable row level security;
alter table public.user_data_permissions enable row level security;

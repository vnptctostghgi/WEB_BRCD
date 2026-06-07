-- Chay file nay trong Supabase Dashboard > SQL Editor
-- Muc dich: bo sung cot nhan vien, phan vung du lieu va quyen du lieu.

alter table public.users add column if not exists employee_code text;
alter table public.users add column if not exists email text;
alter table public.users add column if not exists phone text;
alter table public.users add column if not exists birth_date date;
alter table public.users add column if not exists gender text;
alter table public.users add column if not exists department text;
alter table public.users add column if not exists job_title text;

insert into public.features (code, name, parent_code, sort_order)
values
  ('admin.menu', 'Quản trị menu', 'admin.web', 27),
  ('admin.roles', 'Quản trị vai trò', 'admin.catalogs', 26),
  ('dashboard', 'Tổng quan', null, 10),
  ('admin.web', 'Quản trị web', null, 20),
  ('admin.users', 'Quản trị người dùng', 'admin.web', 21),
  ('admin.connections', 'Quản trị kết nối', 'admin.web', 22),
  ('admin.permissions', 'Phân quyền người dùng', 'admin.web', 23),
  ('admin.data_permissions', 'Phân quyền dữ liệu người dùng', 'admin.web', 24),
  ('admin.catalogs', 'Quản trị danh mục', 'admin.web', 25),
  ('reports', 'Báo cáo thống kê', null, 30),
  ('vault', 'Tài khoản web', 'admin.web', 40),
  ('vault.view', 'Xem danh sách tài khoản', 'vault', 41),
  ('vault.manage', 'Thêm và sửa tài khoản', 'vault', 42),
  ('vault.reveal', 'Xem mật khẩu đã lưu', 'vault', 43),
  ('admin.audit', 'Nhật ký hoạt động', 'admin.web', 90)
on conflict (code) do update
set name = excluded.name,
    parent_code = excluded.parent_code,
    sort_order = excluded.sort_order;

delete from public.user_permissions where feature_code in ('admin', 'admin.connections.test');
delete from public.features where code in ('admin', 'admin.connections.test');

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

create table if not exists public.system_roles (
  code text primary key,
  name text not null,
  description text not null default '',
  is_active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

insert into public.system_roles (code, name, description, is_active, sort_order, created_at, updated_at)
values
  ('admin', 'Quan tri he thong', 'Toan quyen quan tri va cau hinh he thong.', true, 10, now(), now()),
  ('region_manager', 'Quan ly phan vung', 'Quan ly so lieu va nguoi dung theo phan vung duoc cap.', true, 20, now(), now()),
  ('data_entry', 'Nhan vien nhap lieu', 'Nhap va kiem tra du lieu nghiep vu.', true, 30, now(), now()),
  ('viewer', 'Nguoi xem', 'Xem bao cao va chuc nang duoc phan quyen.', true, 40, now(), now())
on conflict (code) do update
set name = excluded.name,
    description = excluded.description,
    is_active = excluded.is_active,
    sort_order = excluded.sort_order,
    updated_at = now();

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
alter table public.system_roles enable row level security;

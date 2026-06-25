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
  ('quantrimenu', 'Quản trị menu', 'quantriweb', 27),
  ('quanlycongviec', 'Quản lý công việc', null, 28),
  ('quantrivaitro', 'Quản trị vai trò', 'quantridanhmuc', 26),
  ('dashboard', 'Tổng quan', null, 10),
  ('quantriweb', 'Quản trị web', null, 20),
  ('quantringuoidung', 'Quản trị người dùng', 'quantriweb', 21),
  ('quantriketnoi', 'Quản trị kết nối', 'quantriweb', 22),
  ('phanquyennguoidung', 'Phân quyền người dùng', 'quantriweb', 23),
  ('phanquyendulieunguoidung', 'Phân quyền dữ liệu người dùng', 'quantriweb', 24),
  ('quantridanhmuc', 'Quản trị danh mục', 'quantriweb', 25),
  ('truyvansql', 'Truy vấn SQL', null, 30),
  ('baocaomoi', 'Báo cáo mới', null, 35),
  ('thietkelayoutbaocao', 'Thiết kế Layout báo cáo', 'baocaomoi', 36),
  ('taikhoanweb', 'Tài khoản web', 'quantriweb', 40),
  ('xemdanhsachtaikhoan', 'Xem danh sách tài khoản', 'taikhoanweb', 41),
  ('themvasuataikhoan', 'Thêm và sửa tài khoản', 'taikhoanweb', 42),
  ('xemmatkhaudaluu', 'Xem mật khẩu đã lưu', 'taikhoanweb', 43),
  ('nhatkyhoatdong', 'Nhật ký hoạt động', 'quantriweb', 90)
on conflict (code) do update
set name = excluded.name,
    parent_code = excluded.parent_code,
    sort_order = excluded.sort_order;

with feature_code_map(old_code, new_code) as (
  values
    ('admin.web', 'quantriweb'),
    ('admin.users', 'quantringuoidung'),
    ('admin.connections', 'quantriketnoi'),
    ('admin.permissions', 'phanquyennguoidung'),
    ('admin.data_permissions', 'phanquyendulieunguoidung'),
    ('admin.catalogs', 'quantridanhmuc'),
    ('admin.roles', 'quantrivaitro'),
    ('admin.menu', 'quantrimenu'),
    ('admin.work_tasks', 'quanlycongviec'),
    ('reports', 'truyvansql'),
    ('new_reports', 'baocaomoi'),
    ('admin.dashboard_builder', 'thietkelayoutbaocao'),
    ('vault', 'taikhoanweb'),
    ('vault.view', 'xemdanhsachtaikhoan'),
    ('vault.manage', 'themvasuataikhoan'),
    ('vault.reveal', 'xemmatkhaudaluu'),
    ('admin.audit', 'nhatkyhoatdong'),
    ('admin.sql_reports', 'quantrisql')
)
insert into public.user_permissions (user_id, feature_code)
select up.user_id, m.new_code
from public.user_permissions up
join feature_code_map m on m.old_code = up.feature_code
on conflict do nothing;

with feature_code_map(old_code, new_code) as (
  values
    ('admin.web', 'quantriweb'),
    ('admin.users', 'quantringuoidung'),
    ('admin.connections', 'quantriketnoi'),
    ('admin.permissions', 'phanquyennguoidung'),
    ('admin.data_permissions', 'phanquyendulieunguoidung'),
    ('admin.catalogs', 'quantridanhmuc'),
    ('admin.roles', 'quantrivaitro'),
    ('admin.menu', 'quantrimenu'),
    ('admin.work_tasks', 'quanlycongviec'),
    ('reports', 'truyvansql'),
    ('new_reports', 'baocaomoi'),
    ('admin.dashboard_builder', 'thietkelayoutbaocao'),
    ('vault', 'taikhoanweb'),
    ('vault.view', 'xemdanhsachtaikhoan'),
    ('vault.manage', 'themvasuataikhoan'),
    ('vault.reveal', 'xemmatkhaudaluu'),
    ('admin.audit', 'nhatkyhoatdong'),
    ('admin.sql_reports', 'quantrisql')
)
update public.features f
set parent_code = m.new_code
from feature_code_map m
where f.parent_code = m.old_code;

delete from public.user_permissions where feature_code in ('admin', 'admin.connections.test', 'auto', 'auto.attt_quarterly', 'auto.attt_links', 'admin.web', 'admin.users', 'admin.connections', 'admin.permissions', 'admin.data_permissions', 'admin.catalogs', 'admin.roles', 'admin.menu', 'admin.work_tasks', 'reports', 'new_reports', 'admin.dashboard_builder', 'vault', 'vault.view', 'vault.manage', 'vault.reveal', 'admin.audit', 'admin.sql_reports');
delete from public.features where code in ('admin', 'admin.connections.test', 'auto', 'auto.attt_quarterly', 'auto.attt_links', 'admin.web', 'admin.users', 'admin.connections', 'admin.permissions', 'admin.data_permissions', 'admin.catalogs', 'admin.roles', 'admin.menu', 'admin.work_tasks', 'reports', 'new_reports', 'admin.dashboard_builder', 'vault', 'vault.view', 'vault.manage', 'vault.reveal', 'admin.audit', 'admin.sql_reports');
insert into public.features (code, name, parent_code, sort_order)
values ('quantrisql', 'Quản trị SQL', 'quantriketnoi', 23)
on conflict (code) do update
set name = excluded.name,
    parent_code = excluded.parent_code,
    sort_order = excluded.sort_order;

drop table if exists public.attt_exam_links;

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

create index if not exists user_data_permissions_region_code_idx
on public.user_data_permissions (region_code);

create index if not exists user_permissions_feature_code_idx
on public.user_permissions (feature_code);

create index if not exists web_credentials_website_id_idx
on public.web_credentials (website_id);


create table if not exists public.system_roles (
  code text primary key,
  name text not null,
  description text not null default '',
  is_active boolean not null default true,
  sort_order integer not null default 0,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.work_tasks (
  task_id text primary key,
  ten_cong_viec text not null,
  schedule_type text not null default 'Daily',
  run_time text not null default '07:00',
  weekday text not null default '',
  once_date date,
  group_name text not null default '',
  is_done boolean not null default false,
  is_active boolean not null default true,
  last_notified_date date,
  last_notified_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.login_attempts (
  username text primary key,
  fail_count integer not null default 0,
  last_ip text not null default '',
  last_failed_at timestamptz not null,
  updated_at timestamptz not null
);

create table if not exists public.sql_reports (
  id bigint generated by default as identity primary key,
  ten_bao_cao text not null,
  ma_bao_cao text not null unique,
  cau_lenh_sql text not null,
  cac_tham_so jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists sql_reports_ma_bao_cao_lower_idx
on public.sql_reports (lower(ma_bao_cao));

create table if not exists public.dashboard_layouts (
  page_id text primary key,
  page_name text not null,
  layout_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.dashboard_chart_cache (
  chart_key text primary key,
  page_id text not null,
  tab_id text not null,
  widget_key text not null,
  report_id bigint,
  sql_code text not null,
  report_code text,
  report_name text,
  widget_title text,
  widget_type text,
  filters jsonb not null default '{}'::jsonb,
  payload jsonb not null default '{}'::jsonb,
  status text not null default 'success' check (status in ('success', 'error', 'refreshing')),
  error_message text,
  duration_ms integer,
  row_count integer not null default 0,
  refreshed_at timestamptz not null default now(),
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists dashboard_chart_cache_report_id_idx
on public.dashboard_chart_cache (report_id);

create index if not exists dashboard_chart_cache_sql_code_idx
on public.dashboard_chart_cache (sql_code);

create index if not exists dashboard_chart_cache_expires_at_idx
on public.dashboard_chart_cache (expires_at);

insert into public.dashboard_layouts (page_id, page_name, layout_json, created_at, updated_at)
values (
  'DASHBOARD_KINH_DOANH',
  'Dashboard Kinh doanh',
  '{
    "page_id": "DASHBOARD_KINH_DOANH",
    "tabs": [
      {
        "tab_id": "tab_doanh_thu",
        "tab_name": "Doanh Thu Lõi",
        "order": 1,
        "grid_layout": [
          {
            "row_id": 1,
            "layout_type": "2_columns",
            "widgets": [
              {"position": 1, "type": "bar_chart", "title": "Di động", "sql_code": "BC_DI_DONG"},
              {"position": 2, "type": "pie_chart", "title": "Băng rộng", "sql_code": "BC_BANG_RONG"}
            ]
          }
        ]
      },
      {
        "tab_id": "tab_san_luong",
        "tab_name": "Sản lượng",
        "order": 2,
        "grid_layout": [
          {
            "row_id": 1,
            "layout_type": "4_columns",
            "widgets": [
              {"position": 1, "type": "metric", "title": "Fiber", "sql_code": "DASHBOARD_FIBER_VNPT"},
              {"position": 2, "type": "metric", "title": "MyTV", "sql_code": "BC_MYTV"},
              {"position": 3, "type": "metric", "title": "Mesh", "sql_code": "BC_MESH"},
              {"position": 4, "type": "metric", "title": "CAM", "sql_code": "BC_CAM"}
            ]
          }
        ]
      }
    ]
  }'::jsonb,
  now(),
  now()
)
on conflict (page_id) do nothing;

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
alter table public.work_tasks enable row level security;
alter table public.login_attempts enable row level security;
alter table public.sql_reports enable row level security;
alter table public.dashboard_layouts enable row level security;
alter table public.dashboard_chart_cache enable row level security;

grant select, insert, update, delete on public.work_tasks to anon, authenticated, service_role;
grant select, insert, update, delete on public.login_attempts to anon, authenticated, service_role;
grant select, insert, update, delete on public.sql_reports to anon, authenticated, service_role;
grant usage, select on sequence public.sql_reports_id_seq to anon, authenticated, service_role;
grant select, insert, update, delete on public.dashboard_layouts to service_role;
grant select, insert, update, delete on public.dashboard_chart_cache to service_role;
grant select on public.dashboard_chart_cache to anon, authenticated;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'dashboard_chart_cache'
      and policyname = 'backend service can manage dashboard chart cache'
  ) then
    create policy "backend service can manage dashboard chart cache"
    on public.dashboard_chart_cache
    for all
    to service_role
    using (true)
    with check (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'dashboard_chart_cache'
      and policyname = 'anon can read dashboard chart cache'
  ) then
    create policy "anon can read dashboard chart cache"
    on public.dashboard_chart_cache
    for select
    to anon
    using (true);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'dashboard_chart_cache'
      and policyname = 'authenticated can read dashboard chart cache'
  ) then
    create policy "authenticated can read dashboard chart cache"
    on public.dashboard_chart_cache
    for select
    to authenticated
    using (true);
  end if;
end $$;

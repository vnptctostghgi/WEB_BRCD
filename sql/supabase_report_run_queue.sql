-- Durable queue shared by the web application and the workstation worker.
-- The web only submits jobs and reads cached results; Oracle access stays on the workstation.

create table if not exists public.report_runs (
    run_id text primary key,
    run_type text not null check (run_type in ('load', 'export', 'dashboard_refresh')),
    report_code text not null default '',
    report_name text not null default '',
    status text not null default 'queued',
    message text not null default '',
    payload jsonb not null default '{}'::jsonb,
    snapshot jsonb not null default '{}'::jsonb,
    details jsonb not null default '{}'::jsonb,
    worker_id text not null default '',
    created_by text not null default 'system',
    row_count integer not null default 0,
    total_rows integer not null default 0,
    file_name text not null default '',
    storage_link text not null default '',
    claimed_at timestamptz,
    started_at timestamptz,
    finished_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists report_runs_queue_idx
    on public.report_runs (status, created_at);

create index if not exists report_runs_type_idx
    on public.report_runs (run_type, created_at desc);

create table if not exists public.report_results (
    run_id text primary key references public.report_runs(run_id) on delete cascade,
    result jsonb not null default '{}'::jsonb,
    columns jsonb not null default '[]'::jsonb,
    rows jsonb not null default '[]'::jsonb,
    pagination jsonb not null default '{}'::jsonb,
    row_count integer not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.report_runs enable row level security;
alter table public.report_results enable row level security;

revoke all on table public.report_runs from anon, authenticated;
revoke all on table public.report_results from anon, authenticated;
grant all on table public.report_runs to service_role;
grant all on table public.report_results to service_role;

comment on table public.report_runs is
    'Service-role-only durable queue for workstation Oracle refresh and export jobs.';
comment on table public.report_results is
    'Service-role-only cached payloads produced by workstation jobs.';

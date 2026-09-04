alter table public.sql_reports
  add column if not exists is_dashboard_source boolean not null default false,
  add column if not exists dashboard_refresh_minutes integer not null default 5,
  add column if not exists dashboard_table_name text not null default '',
  add column if not exists dashboard_last_status text not null default '',
  add column if not exists dashboard_last_error text not null default '',
  add column if not exists dashboard_last_refresh_at timestamptz,
  add column if not exists dashboard_row_count integer not null default 0,
  add column if not exists dashboard_schema_signature text not null default '';

create schema if not exists dashboard_data;
revoke all on schema dashboard_data from public, anon, authenticated;
grant usage on schema dashboard_data to service_role;

create or replace function public.dashboard_replace_dataset(
  p_table_name text,
  p_columns jsonb,
  p_rows jsonb
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, dashboard_data
as $$
declare
  v_table text := lower(trim(p_table_name));
  v_stage text;
  v_backup text;
  v_defs text;
  v_count integer := jsonb_array_length(coalesce(p_rows, '[]'::jsonb));
begin
  if v_table !~ '^[a-z][a-z0-9_]{0,62}$' then
    raise exception 'Invalid dashboard dataset table name';
  end if;
  if jsonb_typeof(p_columns) <> 'array' or jsonb_array_length(p_columns) = 0 then
    raise exception 'Dataset must contain at least one column';
  end if;
  select string_agg(format('%I %s', c->>'name',
    case c->>'type' when 'bigint' then 'bigint' when 'numeric' then 'numeric'
      when 'boolean' then 'boolean' when 'date' then 'date'
      when 'timestamptz' then 'timestamptz' else 'text' end), ', ')
    into v_defs
  from jsonb_array_elements(p_columns) c
  where (c->>'name') ~ '^[a-z][a-z0-9_]{0,62}$';
  if (select count(*) from jsonb_array_elements(p_columns)) <>
     (select count(*) from jsonb_array_elements(p_columns) c where (c->>'name') ~ '^[a-z][a-z0-9_]{0,62}$') then
    raise exception 'Invalid dashboard dataset column name';
  end if;
  v_stage := left(v_table, 45) || '_new_' || substr(md5(clock_timestamp()::text), 1, 8);
  v_backup := left(v_table, 45) || '_old_' || substr(md5(random()::text), 1, 8);
  execute format('create table dashboard_data.%I (%s)', v_stage, v_defs);
  if v_count > 0 then
    execute format('insert into dashboard_data.%I select * from jsonb_populate_recordset(null::dashboard_data.%I, $1)', v_stage, v_stage) using p_rows;
  end if;
  if to_regclass(format('dashboard_data.%I', v_table)) is not null then
    execute format('alter table dashboard_data.%I rename to %I', v_table, v_backup);
  end if;
  execute format('alter table dashboard_data.%I rename to %I', v_stage, v_table);
  execute format('alter table dashboard_data.%I enable row level security', v_table);
  execute format('revoke all on dashboard_data.%I from public, anon, authenticated', v_table);
  execute format('grant select, insert, update, delete on dashboard_data.%I to service_role', v_table);
  if to_regclass(format('dashboard_data.%I', v_backup)) is not null then
    execute format('drop table dashboard_data.%I', v_backup);
  end if;
  return jsonb_build_object('ok', true, 'table_name', v_table, 'row_count', v_count);
exception when others then
  if v_stage is not null and to_regclass(format('dashboard_data.%I', v_stage)) is not null then
    execute format('drop table dashboard_data.%I', v_stage);
  end if;
  raise;
end;
$$;

create or replace function public.dashboard_query_dataset(
  p_table_name text,
  p_query text
) returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, dashboard_data
set statement_timeout = '10s'
as $$
declare
  v_table text := lower(trim(p_table_name));
  v_query text := trim(p_query);
  v_result jsonb;
begin
  if v_table !~ '^[a-z][a-z0-9_]{0,62}$' then raise exception 'Invalid dashboard dataset table name'; end if;
  if v_query !~* '^select[[:space:]]' or v_query ~ ';|--|/\*|\*/' then raise exception 'Only one SELECT statement is allowed'; end if;
  if v_query !~* ('dashboard_data\.' || v_table || '([^a-z0-9_]|$)') then raise exception 'Query must read the selected dashboard table'; end if;
  if v_query ~* '\m(insert|update|delete|drop|alter|create|grant|revoke|truncate|copy|call|do|execute)\M' then raise exception 'Unsafe SQL keyword'; end if;
  execute 'select coalesce(jsonb_agg(to_jsonb(q)), ''[]''::jsonb) from (' || v_query || ') q' into v_result;
  return coalesce(v_result, '[]'::jsonb);
end;
$$;

revoke all on function public.dashboard_replace_dataset(text,jsonb,jsonb) from public, anon, authenticated;
revoke all on function public.dashboard_query_dataset(text,text) from public, anon, authenticated;
grant execute on function public.dashboard_replace_dataset(text,jsonb,jsonb) to service_role;
grant execute on function public.dashboard_query_dataset(text,text) to service_role;
notify pgrst, 'reload schema';

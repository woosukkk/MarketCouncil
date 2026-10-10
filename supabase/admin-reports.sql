begin;
create table if not exists public.admin_reports (
 id uuid primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 kind text not null check(kind in ('monitoring','rag')),
 recorded_at timestamptz not null,
 label text not null check(length(label) between 1 and 120),
 payload jsonb not null check(jsonb_typeof(payload)='object' and octet_length(payload::text)<=1048576),
 created_at timestamptz not null default now()
);
alter table public.admin_reports enable row level security;
revoke all on public.admin_reports from anon,authenticated;
grant select,insert on public.admin_reports to authenticated;
create policy "Editors read measurement reports" on public.admin_reports for select to authenticated using(public.is_official_editor());
create policy "Editors insert own measurement reports" on public.admin_reports for insert to authenticated with check(user_id=(select auth.uid()) and public.is_official_editor());
commit;

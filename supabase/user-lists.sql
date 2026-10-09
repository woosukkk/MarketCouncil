begin;
create table if not exists public.watchlist (
  user_id uuid not null references auth.users(id) on delete cascade,
  company_key text not null check (length(company_key) between 1 and 120),
  company_name text not null check (length(company_name) between 1 and 120),
  ticker text not null default '' check (length(ticker) <= 30),
  created_at timestamptz not null default now(),
  primary key (user_id, company_key)
);
create table if not exists public.saved_analyses (
  user_id uuid not null references auth.users(id) on delete cascade,
  result_key text not null check (result_key ~ '^[a-f0-9]{16}$'),
  company_name text not null check (length(company_name) between 1 and 120),
  analysis_date text not null default '' check (length(analysis_date) <= 50),
  created_at timestamptz not null default now(),
  primary key (user_id, result_key)
);
alter table public.watchlist enable row level security;
alter table public.saved_analyses enable row level security;
revoke all on public.watchlist, public.saved_analyses from anon;
grant select, insert, update, delete on public.watchlist, public.saved_analyses to authenticated;
create policy "Own watchlist only" on public.watchlist for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "Own saved analyses only" on public.saved_analyses for all to authenticated
  using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
commit;

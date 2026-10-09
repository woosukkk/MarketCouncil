begin;
create table public.discussions (
 id uuid primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 company_name text not null check(length(company_name) between 1 and 120),
 ticker text not null default '' check(length(ticker)<=30),
 analysis_date text not null,
 payload jsonb not null check(jsonb_typeof(payload)='object' and octet_length(payload::text)<=2000000),
 visibility text not null default 'private' check(visibility in ('private','public','shared')),
 share_token uuid unique,
 created_at timestamptz not null default now(),
 check ((visibility='shared' and share_token is not null) or (visibility<>'shared' and share_token is null))
);
alter table public.discussions enable row level security;
grant select on public.discussions to anon;
grant select,insert,update,delete on public.discussions to authenticated;
create policy "Read public or own discussion" on public.discussions for select to anon, authenticated
 using (visibility='public' or (select auth.uid())=user_id);
create policy "Insert own private discussion" on public.discussions for insert to authenticated
 with check ((select auth.uid())=user_id and visibility='private' and share_token is null);
create policy "Update own discussion" on public.discussions for update to authenticated
 using ((select auth.uid())=user_id) with check ((select auth.uid())=user_id);
create policy "Delete own discussion" on public.discussions for delete to authenticated using ((select auth.uid())=user_id);
create function public.read_shared_discussion(token uuid) returns jsonb
 language sql stable security definer set search_path='' as $$
 select jsonb_build_object('id',id,'company_name',company_name,'ticker',ticker,'analysis_date',analysis_date,'payload',payload)
 from public.discussions where visibility='shared' and share_token=token;
$$;
revoke all on function public.read_shared_discussion(uuid) from public;
grant execute on function public.read_shared_discussion(uuid) to anon,authenticated;
create table public.official_editors (user_id uuid primary key references auth.users(id) on delete cascade);
alter table public.official_editors enable row level security;
revoke all on public.official_editors from anon,authenticated;
create table public.daily_official_discussions (
 publication_date date primary key,
 discussion_id uuid not null references public.discussions(id) on delete cascade
);
alter table public.daily_official_discussions enable row level security;
grant select on public.daily_official_discussions to anon,authenticated;
revoke insert,update,delete on public.daily_official_discussions from anon,authenticated;
create policy "Read official selections" on public.daily_official_discussions for select to anon,authenticated using (true);
create function public.is_official_editor() returns boolean
 language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.official_editors where user_id=(select auth.uid()));
$$;
revoke all on function public.is_official_editor() from public;
grant execute on function public.is_official_editor() to authenticated;
create function public.select_daily_official(discussion uuid) returns date
 language plpgsql security definer set search_path='' as $$
declare day date := (now() at time zone 'Asia/Seoul')::date;
begin
 if not exists(select 1 from public.official_editors where user_id=auth.uid()) then raise exception 'Not authorized'; end if;
 update public.discussions set visibility='public',share_token=null where id=discussion and user_id=auth.uid();
 if not found then raise exception 'Own discussion required'; end if;
 insert into public.daily_official_discussions(publication_date,discussion_id) values(day,discussion)
 on conflict(publication_date) do update set discussion_id=excluded.discussion_id;
 return day;
end;
$$;
revoke all on function public.select_daily_official(uuid) from public;
grant execute on function public.select_daily_official(uuid) to authenticated;
commit;

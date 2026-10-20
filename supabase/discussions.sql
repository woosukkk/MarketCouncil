begin;
-- Keep this function identical to the fresh-install definition in discussions.sql.
create or replace function public.valid_discussion_result(payload jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare
 path text;
 node jsonb;
 item jsonb;
 key_name text;
begin
 if payload is null or jsonb_typeof(payload) <> 'object'
    or jsonb_typeof(payload->'company_name') is distinct from 'string'
    or length(payload->>'company_name') not between 1 and 120
    or (payload->>'company_name') !~ '[^[:space:]]'
    or jsonb_typeof(payload->'rounds') is distinct from 'array' then return false; end if;

 foreach path in array array['$.financial_data','$.navigation','$.moderator_summary',
   '$.rounds[*].bull_response','$.rounds[*].bear_response','$.rounds[*].moderator_review'] loop
  for node in select jsonb_path_query(payload,path::jsonpath) loop
   if node <> 'null'::jsonb and jsonb_typeof(node) <> 'object' then return false; end if;
  end loop;
 end loop;
 foreach path in array array['$.rounds','$.agenda','$.issue_statuses','$.navigation.issues',
   '$.rounds[*].bull_response.issues','$.rounds[*].bear_response.issues','$.rounds[*].moderator_review.issue_reviews'] loop
  for node in select jsonb_path_query(payload,path::jsonpath) loop
   if node = 'null'::jsonb then continue; end if;
   if jsonb_typeof(node) <> 'array' then return false; end if;
   if jsonb_array_length(node)>1000 then return false; end if;
   if exists(select 1 from jsonb_array_elements(node) value where jsonb_typeof(value)<>'object') then return false; end if;
  end loop;
 end loop;
 foreach path in array array['$.created_at','$.bull_analysis','$.bear_analysis',
   '$.financial_data.ticker','$.financial_data.price_date','$.navigation.overview',
   '$.moderator_summary.summary','$.moderator_summary.headline','$.moderator_summary.lead'] loop
  for node in select jsonb_path_query(payload,path::jsonpath) loop
   if jsonb_typeof(node) not in ('null','string') then return false; end if;
  end loop;
 end loop;
 foreach path in array array['$.moderator_summary.agreements','$.moderator_summary.unresolved_issues','$.moderator_summary.required_evidence'] loop
  for node in select jsonb_path_query(payload,path::jsonpath) loop
   if node='null'::jsonb then continue; end if;
   if jsonb_typeof(node)<>'array' then return false; end if;
   if jsonb_array_length(node)>1000 then return false; end if;
   if exists(select 1 from jsonb_array_elements(node) value where jsonb_typeof(value)<>'string') then return false; end if;
  end loop;
 end loop;
 for node in select jsonb_path_query(payload,'$.rounds[*].round') loop
  if jsonb_typeof(node) not in ('null','string','number') then return false; end if;
 end loop;
 foreach path in array array['$.agenda[*]','$.issue_statuses[*]','$.navigation.issues[*]',
   '$.rounds[*].bull_response.issues[*]','$.rounds[*].bear_response.issues[*]','$.rounds[*].moderator_review.issue_reviews[*]'] loop
  for node in select jsonb_path_query(payload,path::jsonpath) loop
   foreach key_name in array array['issue_id','title','question','bull_claim','bear_claim','claim','warrant','qualifier','status','assessment','core_disagreement'] loop
    if node ? key_name and jsonb_typeof(node->key_name) not in ('null','string') then return false; end if;
   end loop;
   if node ? 'missing_evidence' and jsonb_typeof(node->'missing_evidence') not in ('null','string') then
    if jsonb_typeof(node->'missing_evidence')<>'array' then return false; end if;
    if jsonb_array_length(node->'missing_evidence')>1000 then return false; end if;
    if exists(select 1 from jsonb_array_elements(node->'missing_evidence') value where jsonb_typeof(value)<>'string') then return false; end if;
   end if;
   if node ? 'evidence' and node->'evidence'<>'null'::jsonb then
    if jsonb_typeof(node->'evidence')<>'array' then return false; end if;
    if jsonb_array_length(node->'evidence')>1000 then return false; end if;
    for item in select jsonb_array_elements(node->'evidence') loop
     if jsonb_typeof(item) in ('null','string') then continue; end if;
     if jsonb_typeof(item)<>'object' then return false; end if;
     foreach key_name in array array['evidence_id','source_id','exact_quote','reason','title','source_type','source_url','published_at','source_page_url','context_text'] loop
      if item ? key_name and jsonb_typeof(item->key_name) not in ('null','string') then return false; end if;
     end loop;
     if item ? 'verified' and jsonb_typeof(item->'verified') not in ('null','boolean') then return false; end if;
     if item ? 'page_number' and jsonb_typeof(item->'page_number') not in ('null','string','number') then return false; end if;
    end loop;
   end if;
  end loop;
 end loop;
 return true;
end;
$$;

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
create or replace function public.enforce_discussion_result() returns trigger
 language plpgsql set search_path='' as $$
begin
 -- Legacy rows can always be withdrawn; changed payloads and new publications are validated.
 if TG_OP='INSERT' or new.payload is distinct from old.payload
    or (new.visibility in ('public','shared') and (new.visibility is distinct from old.visibility
        or new.share_token is distinct from old.share_token)) then
  if not public.valid_discussion_result(new.payload) then
   raise exception 'Invalid discussion result' using errcode='23514',constraint='discussions_payload_shape';
  end if;
 end if;
 return new;
end;
$$;
revoke all on function public.enforce_discussion_result() from public,anon,authenticated;
drop trigger if exists enforce_discussion_result on public.discussions;
create trigger enforce_discussion_result before insert or update of payload,visibility,share_token on public.discussions
 for each row execute function public.enforce_discussion_result();
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
create function public.is_official_editor() returns boolean
 language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.official_editors where user_id=(select auth.uid()));
$$;
revoke all on function public.is_official_editor() from public,anon;
grant execute on function public.is_official_editor() to authenticated;
create or replace function public.remove_withdrawn_official() returns trigger
 language plpgsql security definer set search_path='' as $$
begin
 delete from public.daily_official_discussions where discussion_id=new.id;
 return new;
end;
$$;
revoke all on function public.remove_withdrawn_official() from public,anon,authenticated;
drop trigger if exists remove_withdrawn_official on public.discussions;
create trigger remove_withdrawn_official after update of visibility on public.discussions
 for each row when (new.visibility<>'public') execute function public.remove_withdrawn_official();
drop policy if exists "Read official selections" on public.daily_official_discussions;
create policy "Read official selections" on public.daily_official_discussions for select to anon,authenticated
 using (exists(select 1 from public.discussions d where d.id=discussion_id and d.visibility='public'));
-- Remove stale selection metadata only; the discussion and its payload are retained.
delete from public.daily_official_discussions s using public.discussions d
 where d.id=s.discussion_id and d.visibility<>'public';
drop function if exists public.select_daily_official(uuid);
create or replace function public.select_daily_official(
 discussion uuid,
 expected_day date default (clock_timestamp() at time zone 'Asia/Seoul')::date,
 replace_existing boolean default false
) returns date language plpgsql security definer set search_path='' as $$
declare
 day date := (clock_timestamp() at time zone 'Asia/Seoul')::date;
 selected uuid;
 result_payload jsonb;
begin
 if not exists(select 1 from public.official_editors where user_id=auth.uid()) then raise exception 'Not authorized'; end if;
 if expected_day is distinct from day then raise exception 'official_date_changed'; end if;
 -- Serialize competing operators before publishing either result.
 perform pg_advisory_xact_lock(hashtextextended('daily_official:' || day::text,0));
 select payload into result_payload from public.discussions where id=discussion and user_id=auth.uid() for update;
 if not found then raise exception 'Own discussion required'; end if;
 if day is distinct from (clock_timestamp() at time zone 'Asia/Seoul')::date then raise exception 'official_date_changed'; end if;
 if not public.valid_discussion_result(result_payload) then raise exception 'Invalid discussion result' using errcode='23514'; end if;
 select discussion_id into selected from public.daily_official_discussions where publication_date=day;
 if selected is not null and selected<>discussion and not coalesce(replace_existing,false) then
  raise exception 'official_selection_conflict';
 end if;
 update public.discussions set visibility='public',share_token=null where id=discussion;
 insert into public.daily_official_discussions(publication_date,discussion_id) values(day,discussion)
 on conflict(publication_date) do update set discussion_id=excluded.discussion_id;
 return day;
end;
$$;
revoke all on function public.select_daily_official(uuid,date,boolean) from public,anon;
grant execute on function public.select_daily_official(uuid,date,boolean) to authenticated;
commit;

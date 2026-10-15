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
 payload jsonb not null check(jsonb_typeof(payload)='object' and octet_length(payload::text)<=2000000)
   constraint discussions_payload_shape check(public.valid_discussion_result(payload)),
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

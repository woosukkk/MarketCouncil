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

-- A NOT VALID CHECK still checks every UPDATE, including a legacy privacy withdrawal.
alter table public.discussions drop constraint if exists discussions_payload_shape;
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
commit;

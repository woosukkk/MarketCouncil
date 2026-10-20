begin;
-- Supabase default privileges may grant anon directly, independently of PUBLIC.
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

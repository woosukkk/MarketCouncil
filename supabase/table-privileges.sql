begin;
-- Apply to databases created before discussions.sql and user-lists.sql revoked Supabase default table privileges.
-- Keep only the privileges the RLS policies use; TRUNCATE, REFERENCES and TRIGGER are not limited by RLS.
-- Safe to run more than once. Run after discussions.sql and user-lists.sql.
revoke all on public.discussions, public.daily_official_discussions, public.watchlist, public.saved_analyses
 from anon, authenticated;
grant select on public.discussions, public.daily_official_discussions to anon;
grant select on public.daily_official_discussions to authenticated;
grant select, insert, update, delete on public.discussions, public.watchlist, public.saved_analyses to authenticated;
commit;

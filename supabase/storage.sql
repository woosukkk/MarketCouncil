begin;
-- Public-read bucket for reviewed analysis results (docs/result-publishing.md).
-- No storage.objects policies are defined, so anon and authenticated clients cannot upload, replace or delete objects.
-- Safe to run more than once.
insert into storage.buckets (id, name, public)
values ('analysis-results', 'analysis-results', true)
on conflict (id) do update set public = excluded.public;
commit;

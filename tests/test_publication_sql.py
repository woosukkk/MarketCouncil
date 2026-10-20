"""Opt-in PostgreSQL integration tests; no host ports or persistent volumes are used.

Run with MARKETCOUNCIL_TEST_POSTGRES=1 and the local postgres:17-alpine image.
"""
import os
import json
import copy
from pathlib import Path
import subprocess
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


@unittest.skipUnless(os.environ.get("MARKETCOUNCIL_TEST_POSTGRES") == "1", "opt-in local PostgreSQL test")
class PublicationSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.container = "marketcouncil-publication-test-" + uuid.uuid4().hex[:12]
        subprocess.run(["docker", "run", "--detach", "--name", cls.container,
                        "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17-alpine"],
                       check=True, capture_output=True, text=True)
        try:
            for _ in range(100):
                ready = subprocess.run(["docker", "exec", cls.container, "pg_isready", "-U", "postgres"], capture_output=True)
                if ready.returncode == 0:
                    break
                time.sleep(.2)
            else:
                raise RuntimeError("Temporary PostgreSQL did not start")
            cls.sql("""
                create role anon nologin;
                create role authenticated nologin;
                alter default privileges in schema public grant execute on functions to anon,authenticated;
                create schema auth;
                create table auth.users(id uuid primary key);
                create function auth.uid() returns uuid language sql stable as $$
                  select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
                $$;
                grant usage on schema auth to anon,authenticated;
            """)
            cls.sql((ROOT / "supabase/discussions.sql").read_text(encoding="utf-8"))
            cls.sql(f"insert into auth.users values ('{OWNER}'),('{OTHER}');")
        except BaseException:
            subprocess.run(["docker", "rm", "-f", cls.container], capture_output=True)
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        subprocess.run(["docker", "rm", "-f", cls.container], check=True, capture_output=True)

    @classmethod
    def sql(cls, text: str, check: bool = True) -> str:
        result = subprocess.run(["docker", "exec", "-i", cls.container, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "postgres"],
                                input=text, text=True, encoding="utf-8", capture_output=True)
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()

    @classmethod
    def owner_sql(cls, text: str, user: str = OWNER, check: bool = True) -> str:
        return cls.sql(f"set role authenticated; set request.jwt.claim.sub='{user}'; " + text, check)

    def setUp(self) -> None:
        self.sql("truncate public.official_editors,public.discussions cascade;")
        self.sql(f"insert into public.official_editors values ('{OWNER}');")
        for identifier in (A, B):
            self.owner_sql(f"insert into public.discussions(id,user_id,company_name,analysis_date,payload) values ('{identifier}','{OWNER}','Example','2026-10-16',jsonb_build_object('company_name','Example','rounds',jsonb_build_array()));")

    def select(self, identifier: str, replace: bool = False, check: bool = True) -> str:
        return self.owner_sql(f"select public.select_daily_official('{identifier}',(clock_timestamp() at time zone 'Asia/Seoul')::date,{str(replace).lower()});", check=check)

    def test_function_acl_restricts_supabase_defaults_and_existing_anon_grants(self) -> None:
        expected = {
            "is_official_editor()": "f|t",
            "select_daily_official(uuid,date,boolean)": "f|t",
            "enforce_discussion_result()": "f|f",
            "remove_withdrawn_official()": "f|f",
            "valid_discussion_result(jsonb)": "t|t",
            "read_shared_discussion(uuid)": "t|t",
        }

        def check_acl() -> None:
            for signature, privileges in expected.items():
                with self.subTest(function=signature):
                    self.assertEqual(self.sql(
                        f"select has_function_privilege('anon','public.{signature}','EXECUTE'),"
                        f"has_function_privilege('authenticated','public.{signature}','EXECUTE');"
                    ), privileges)

        check_acl()
        for signature in tuple(expected)[:4]:
            self.sql(f"grant execute on function public.{signature} to anon,authenticated;")
        for _ in range(2):
            for filename in ("discussion-result-validation.sql", "discussion-publication-state.sql"):
                self.sql((ROOT / "supabase" / filename).read_text(encoding="utf-8"))
            check_acl()

    def test_sql_validator_matches_shared_web_and_desktop_contract(self) -> None:
        fixture = json.loads((ROOT / "frontend/tests/result-validation-cases.json").read_text(encoding="utf-8"))
        values = []
        for index, row in enumerate(fixture["cases"]):
            payload = row.get("result", {**copy.deepcopy(fixture["base"]), **row.get("fields", {})})
            encoded = json.dumps(payload, ensure_ascii=True).replace("'", "''")
            values.append(f"({index},'{encoded}'::jsonb)")
        results = self.sql("select public.valid_discussion_result(payload) from (values " + ",".join(values) + ") as cases(n,payload) order by n;").splitlines()
        self.assertEqual(results, ["t" if row["valid"] else "f" for row in fixture["cases"]])

    def test_conflict_is_atomic_and_manual_replacement_is_explicit(self) -> None:
        self.select(A)
        self.assertEqual(self.select(A), self.select(A))
        self.assertIn("official_selection_conflict", self.select(B, check=False))
        self.assertEqual(self.sql(f"select visibility from public.discussions where id='{B}';"), "private")
        self.assertEqual(self.sql("select discussion_id from public.daily_official_discussions;"), A)
        self.select(B, replace=True)
        self.assertEqual(self.sql("select discussion_id from public.daily_official_discussions;"), B)
        self.assertEqual(self.sql(f"select visibility from public.discussions where id='{B}';"), "public")

    def test_withdrawal_removes_selections_without_deleting_payload(self) -> None:
        for visibility, token in (("private", "null"), ("shared", "'cccccccc-cccc-4ccc-8ccc-cccccccccccc'")):
            self.select(A)
            self.owner_sql(f"update public.discussions set visibility='{visibility}',share_token={token} where id='{A}';")
            self.assertEqual(self.sql("select count(*) from public.daily_official_discussions;"), "0")
            self.assertEqual(self.sql(f"select payload->>'company_name' from public.discussions where id='{A}';"), "Example")
            self.assertEqual(self.sql("set role anon; select count(*) from public.discussions;"), "0")

    def test_legacy_invalid_payload_can_be_withdrawn_but_not_published(self) -> None:
        self.sql("alter table public.discussions disable trigger enforce_discussion_result;")
        self.sql(f"update public.discussions set payload=jsonb_build_object('company_name','Example','rounds','invalid'),visibility='public' where id='{A}';")
        self.sql("alter table public.discussions enable trigger enforce_discussion_result;")
        self.sql("alter table public.discussions add constraint discussions_payload_shape check(public.valid_discussion_result(payload)) not valid;")
        before = self.owner_sql(f"update public.discussions set visibility='private' where id='{A}';", check=False)
        self.assertIn('violates check constraint "discussions_payload_shape"', before)
        self.assertEqual(self.sql(f"select visibility from public.discussions where id='{A}';"), "public")
        self.sql((ROOT / "supabase/discussion-result-validation.sql").read_text(encoding="utf-8"))
        self.sql((ROOT / "supabase/discussion-result-validation.sql").read_text(encoding="utf-8"))
        self.owner_sql(f"update public.discussions set visibility='private' where id='{A}';")
        self.assertIn("Invalid discussion result", self.owner_sql(f"update public.discussions set visibility='public' where id='{A}';", check=False))
        self.assertIn("Invalid discussion result", self.select(A, check=False))
        self.assertIn("Invalid discussion result", self.owner_sql(f"update public.discussions set payload=jsonb_build_object('company_name','bad') where id='{B}';", check=False))
        self.assertIn("Invalid discussion result", self.owner_sql(f"insert into public.discussions(id,user_id,company_name,analysis_date,payload) values ('dddddddd-dddd-4ddd-8ddd-dddddddddddd','{OWNER}','bad','today','{{}}');", check=False))

    def test_invalid_legacy_share_cannot_be_rotated_into_a_new_link(self) -> None:
        self.sql("alter table public.discussions disable trigger enforce_discussion_result;")
        self.sql(f"update public.discussions set payload=jsonb_build_object('company_name','bad'),visibility='shared',share_token='cccccccc-cccc-4ccc-8ccc-cccccccccccc' where id='{A}';")
        self.sql("alter table public.discussions enable trigger enforce_discussion_result;")
        result = self.owner_sql(f"update public.discussions set share_token='dddddddd-dddd-4ddd-8ddd-dddddddddddd' where id='{A}';", check=False)
        self.assertIn("Invalid discussion result", result)
        self.owner_sql(f"update public.discussions set visibility='private',share_token=null where id='{A}';")
        self.assertEqual(self.sql(f"select visibility from public.discussions where id='{A}';"), "private")

    def test_stale_reference_is_hidden_then_migration_cleans_only_metadata(self) -> None:
        self.sql(f"insert into public.daily_official_discussions values (current_date,'{A}');")
        self.assertEqual(self.sql("set role anon; select count(*) from public.daily_official_discussions;"), "0")
        self.sql((ROOT / "supabase/discussion-publication-state.sql").read_text(encoding="utf-8"))
        self.sql((ROOT / "supabase/discussion-publication-state.sql").read_text(encoding="utf-8"))
        self.assertEqual(self.sql("select count(*) from public.daily_official_discussions;"), "0")
        self.assertEqual(self.sql("select count(*) from public.discussions;"), "2")

    def test_null_schema_probe_never_publishes_or_changes_a_selection(self) -> None:
        for has_selection in (False, True):
            if has_selection:
                self.select(A)
            before = self.sql("select coalesce(string_agg(discussion_id::text,','),'') from public.daily_official_discussions;")
            result = self.owner_sql("select public.select_daily_official(null,(clock_timestamp() at time zone 'Asia/Seoul')::date,false);", check=False)
            self.assertIn("Own discussion required", result)
            self.assertEqual(self.sql("select coalesce(string_agg(discussion_id::text,','),'') from public.daily_official_discussions;"), before)
            self.assertEqual(self.sql(f"select visibility from public.discussions where id='{B}';"), "private")

    def test_wrong_day_and_unauthorized_cannot_publish(self) -> None:
        result = self.owner_sql(f"select public.select_daily_official('{A}',(clock_timestamp() at time zone 'Asia/Seoul')::date-1,false);", check=False)
        self.assertIn("official_date_changed", result)
        self.assertIn("Not authorized", self.owner_sql(f"select public.select_daily_official('{A}');", user=OTHER, check=False))
        self.sql(f"insert into public.official_editors values ('{OTHER}');")
        self.assertIn("Own discussion required", self.owner_sql(f"select public.select_daily_official('{A}');", user=OTHER, check=False))
        self.assertEqual(self.sql("select count(*) from public.daily_official_discussions;"), "0")

    def test_rls_and_delete_cascade(self) -> None:
        self.assertEqual(self.owner_sql("select count(*) from public.discussions;", user=OTHER), "0")
        self.owner_sql(f"update public.discussions set visibility='public' where id='{A}';", user=OTHER)
        self.assertEqual(self.sql(f"select visibility from public.discussions where id='{A}';"), "private")
        self.select(A)
        self.assertEqual(self.sql("set role anon; select count(*) from public.daily_official_discussions;"), "1")
        self.owner_sql(f"delete from public.discussions where id='{A}';")
        self.assertEqual(self.sql("select count(*) from public.daily_official_discussions;"), "0")

    def test_concurrent_automatic_selection_has_one_winner(self) -> None:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda identifier: self.select(identifier, check=False), (A, B)))
        self.assertEqual(sum("official_selection_conflict" in result for result in results), 1)
        self.assertEqual(self.sql("select count(*) from public.daily_official_discussions;"), "1")
        self.assertEqual(self.sql("select count(*) from public.discussions where visibility='public';"), "1")


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from app import local_services as services


class DailyServicesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"MANAGE_LOCAL_SERVICES": "true"}))
        self.stack.enter_context(patch.object(services.COMPOSE_FILE.__class__, "exists", return_value=True))
        self.ready = self.stack.enter_context(patch.object(services, "_service_ready", return_value=False))
        self.docker = self.stack.enter_context(patch.object(services, "_docker_ready", return_value=True))
        self.ensure = self.stack.enter_context(patch.object(services, "ensure_local_services"))
        self.ids = self.stack.enter_context(patch.object(services, "_running_container_ids", side_effect=[set(), {"new"}]))
        self.cleanup = self.stack.enter_context(patch.object(services, "_cleanup_command"))
        self.stopped = self.stack.enter_context(patch.object(services, "_desktop_stopped", return_value=False))
        self.start = self.stack.enter_context(patch.object(services, "_start_docker_desktop"))
        self.wait = self.stack.enter_context(patch.object(services, "_wait_until"))

    def test_existing_ready_service_is_untouched(self) -> None:
        self.ready.return_value = True
        with services.daily_local_services():
            pass
        self.ensure.assert_called_once()
        self.docker.assert_not_called()
        self.ids.assert_not_called()
        self.cleanup.assert_not_called()

    def test_external_service_is_untouched(self) -> None:
        with patch.dict(os.environ, {"MANAGE_LOCAL_SERVICES": "false"}):
            with services.daily_local_services():
                pass
        self.ensure.assert_called_once()
        self.docker.assert_not_called()
        self.cleanup.assert_not_called()

    def test_new_container_stops_but_existing_desktop_stays(self) -> None:
        with services.daily_local_services():
            self.cleanup.assert_not_called()
        self.cleanup.assert_called_once_with(["docker", "stop", "--time", "10", "new"], "SearXNG")
        self.start.assert_not_called()

    def test_existing_container_is_preserved_on_readiness_failure(self) -> None:
        self.ids.side_effect = [{"existing"}, {"existing"}]
        self.ensure.side_effect = RuntimeError("not ready")
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            with services.daily_local_services():
                self.fail("Readiness must fail before entering the body")
        self.cleanup.assert_not_called()

    def test_partial_start_is_cleaned_when_readiness_fails(self) -> None:
        self.ensure.side_effect = RuntimeError("not ready")
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            with services.daily_local_services():
                pass
        self.cleanup.assert_called_once_with(["docker", "stop", "--time", "10", "new"], "SearXNG")

    def test_body_failure_still_cleans_only_new_container(self) -> None:
        self.ids.side_effect = [{"existing"}, {"existing", "new"}]
        with self.assertRaisesRegex(RuntimeError, "publish failed"):
            with services.daily_local_services():
                raise RuntimeError("publish failed")
        self.cleanup.assert_called_once_with(["docker", "stop", "--time", "10", "new"], "SearXNG")

    def test_task_started_desktop_and_autoresumed_project_are_cleaned(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.ids.side_effect = [{"autoresumed"}, set()]
        with services.daily_local_services():
            pass
        self.start.assert_called_once()
        self.assertEqual(self.ids.call_args_list[0].kwargs, {"compose_only": True})
        self.assertEqual(self.cleanup.call_count, 2)
        self.assertEqual(self.cleanup.call_args_list[0].args[0], ["docker", "stop", "--time", "10", "autoresumed"])
        self.assertEqual(self.cleanup.call_args_list[1].args[0], ["docker", "desktop", "stop", "--timeout", "30"])

    def test_other_running_container_keeps_task_started_desktop_open(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.ids.side_effect = [{"new"}, {"other-project"}]
        with services.daily_local_services():
            pass
        self.cleanup.assert_called_once_with(["docker", "stop", "--time", "10", "new"], "SearXNG")

    def test_unknown_desktop_status_is_not_owned(self) -> None:
        self.docker.return_value = False
        with services.daily_local_services():
            pass
        self.start.assert_called_once()
        self.cleanup.assert_called_once_with(["docker", "stop", "--time", "10", "new"], "SearXNG")

    def test_unknown_container_baseline_never_stops_a_container(self) -> None:
        self.ids.side_effect = [None]
        with services.daily_local_services():
            pass
        self.ensure.assert_called_once()
        self.cleanup.assert_not_called()

    def test_failed_container_queries_keep_desktop_open(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.ids.side_effect = [None, None]
        with services.daily_local_services():
            pass
        self.cleanup.assert_not_called()

    def test_engine_start_timeout_keeps_original_error(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.wait.side_effect = RuntimeError("engine timeout")
        self.ids.side_effect = [None, set()]
        with self.assertRaisesRegex(RuntimeError, "engine timeout"):
            with services.daily_local_services():
                pass
        self.cleanup.assert_called_once_with(["docker", "desktop", "stop", "--timeout", "30"], "Docker Desktop")
        self.ensure.assert_not_called()

    def test_failed_desktop_start_never_stops_existing_processes(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.start.side_effect = RuntimeError("start failed")
        self.ids.side_effect = [None, None]
        with self.assertRaisesRegex(RuntimeError, "start failed"):
            with services.daily_local_services():
                pass
        self.cleanup.assert_not_called()


    def test_partial_desktop_start_failure_cleans_owned_resources(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.start.side_effect = RuntimeError("start timed out after partial startup")
        self.ids.side_effect = [{"new"}, set()]
        with self.assertRaisesRegex(RuntimeError, "start timed out after partial startup"):
            with services.daily_local_services():
                self.fail("Body must not run after failed startup")
        self.assertEqual([call.args[0] for call in self.cleanup.call_args_list], [
            ["docker", "stop", "--time", "10", "new"],
            ["docker", "desktop", "stop", "--timeout", "30"],
        ])
        self.ensure.assert_not_called()

    def test_successful_cleanup_does_not_report_error(self) -> None:
        self.cleanup.return_value = True
        report = Mock()
        with services.daily_local_services(on_cleanup_error=report):
            pass
        report.assert_not_called()

    def test_cleanup_failure_reports_only_fixed_service_label(self) -> None:
        self.docker.return_value = False
        self.stopped.return_value = True
        self.ids.side_effect = [{"new"}, set()]
        self.cleanup.return_value = False
        report = Mock()
        with services.daily_local_services(on_cleanup_error=report):
            pass
        self.assertEqual([call.args for call in report.call_args_list], [("SearXNG",), ("Docker Desktop",)])

    def test_error_callback_never_replaces_original_publish_failure(self) -> None:
        self.cleanup.return_value = False
        report = Mock(side_effect=RuntimeError("error log unavailable"))
        with self.assertRaisesRegex(RuntimeError, "publish failed"):
            with services.daily_local_services(on_cleanup_error=report):
                raise RuntimeError("publish failed")
        report.assert_called_once_with("SearXNG")


class DockerCommandSafetyTests(unittest.TestCase):
    def test_query_failure_and_unexpected_output_fail_closed(self) -> None:
        for result in (Mock(returncode=1, stdout=""), Mock(returncode=0, stdout="unexpected output"),
                       Mock(returncode=0, stdout="abc123")):
            with self.subTest(result=result), patch.object(services.subprocess, "run", return_value=result):
                self.assertIsNone(services._running_container_ids(compose_only=True))
        for error in (OSError(), subprocess.TimeoutExpired("docker", 15)):
            with self.subTest(error=error), patch.object(services.subprocess, "run", side_effect=error):
                self.assertIsNone(services._running_container_ids())

    def test_container_queries_are_scoped_and_bounded(self) -> None:
        with patch.object(services.subprocess, "run", return_value=Mock(returncode=0, stdout="abc123abc123\n")) as run:
            self.assertEqual(services._running_container_ids(compose_only=True), {"abc123abc123"})
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["docker", "compose", "-f", str(services.COMPOSE_FILE)])
        self.assertEqual(command[-1], "searxng")
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_desktop_ownership_requires_explicit_stopped_status(self) -> None:
        with patch.object(services.os, "name", "nt"):
            for output, expected in (('{"Status":"stopped"}', True), ('{"Status":"running"}', False), ('{"Status":"starting"}', False), ("bad json", False), ("[]", False)):
                with self.subTest(output=output), patch.object(services.subprocess, "run", return_value=Mock(returncode=0, stdout=output)):
                    self.assertEqual(services._desktop_stopped(), expected)
            with patch.object(services.subprocess, "run", return_value=Mock(returncode=1, stdout='{"Status":"stopped"}')):
                self.assertFalse(services._desktop_stopped())

    def test_stopped_cli_falls_back_to_valid_process_inventory(self) -> None:
        processes = '"python.exe","1234","Console","1","12,000 K"\n'
        with patch.object(services.os, "name", "nt"), patch.object(services.subprocess, "run", side_effect=[
            Mock(returncode=1, stdout=""), Mock(returncode=0, stdout=processes),
        ]) as run:
            self.assertTrue(services._desktop_stopped())
        self.assertEqual(run.call_args.args[0], ["tasklist", "/FO", "CSV", "/NH"])
        self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_process_inventory_preserves_desktop_and_backend(self) -> None:
        for name in ("Docker Desktop.exe", "com.docker.backend.exe"):
            with self.subTest(name=name), patch.object(services.os, "name", "nt"), patch.object(
                services.subprocess, "run", side_effect=[
                    Mock(returncode=1, stdout=""),
                    Mock(returncode=0, stdout=f'"{name}","1234","Console","1","12,000 K"\n'),
                ]
            ):
                self.assertFalse(services._desktop_stopped())

    def test_unknown_process_inventory_cannot_prove_desktop_stopped(self) -> None:
        for result in (Mock(returncode=1, stdout=""), Mock(returncode=0, stdout=""),
                       Mock(returncode=0, stdout="malformed output"),
                       Mock(returncode=0, stdout='"python.exe","not-pid","Console","1","12 K"'),
                       Mock(returncode=0, stdout='"unterminated')):
            with self.subTest(result=result), patch.object(services.os, "name", "nt"), patch.object(
                services.subprocess, "run", side_effect=[Mock(returncode=1, stdout=""), result]
            ):
                self.assertFalse(services._desktop_stopped())
        with patch.object(services.os, "name", "nt"), patch.object(services.subprocess, "run", side_effect=[
            Mock(returncode=1, stdout=""), subprocess.TimeoutExpired("tasklist", 15),
        ]):
            self.assertFalse(services._desktop_stopped())

    def test_desktop_start_uses_bounded_hidden_official_cli(self) -> None:
        with patch.object(services.os, "name", "nt"), patch.object(
            services.DOCKER_DESKTOP.__class__, "exists", return_value=True
        ), patch.object(services.subprocess, "run", return_value=Mock(returncode=0)) as run:
            services._start_docker_desktop()
        self.assertEqual(run.call_args.args[0], ["docker", "desktop", "start", "--detach", "--timeout", "30"])
        self.assertTrue(run.call_args.kwargs["check"])
        self.assertEqual(run.call_args.kwargs["timeout"], 40)
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")
        if os.name == "nt":
            self.assertEqual(run.call_args.kwargs["creationflags"], subprocess.CREATE_NO_WINDOW)

    def test_desktop_start_errors_preserve_cause_without_cli_details(self) -> None:
        for error in (OSError("private diagnostic"), subprocess.TimeoutExpired("docker", 40),
                      subprocess.CalledProcessError(1, "docker", stderr="private diagnostic")):
            with self.subTest(error=error), patch.object(services.os, "name", "nt"), patch.object(
                services.DOCKER_DESKTOP.__class__, "exists", return_value=True
            ), patch.object(services.subprocess, "run", side_effect=error):
                with self.assertRaises(RuntimeError) as raised:
                    services._start_docker_desktop()
                self.assertIs(raised.exception.__cause__, error)
                self.assertNotIn("private", str(raised.exception))

    def test_cleanup_decodes_utf8_output_from_real_child_process(self) -> None:
        real_run = subprocess.run
        captured: dict[str, object] = {}

        def capture(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            self.assertEqual(kwargs.get("encoding"), "utf-8")
            self.assertEqual(kwargs.get("errors"), "replace")
            result = real_run(command, **kwargs)
            captured["result"] = result
            return result

        child = "import sys;sys.stdout.buffer.write(bytes.fromhex('e29c93'));sys.stderr.buffer.write(bytes.fromhex('e29c93'))"
        with patch.object(services.subprocess, "run", side_effect=capture):
            self.assertTrue(services._cleanup_command([sys.executable, "-c", child], "SearXNG"))
        result = captured["result"]
        self.assertEqual(result.stdout, "\u2713")
        self.assertEqual(result.stderr, "\u2713")

    def test_cleanup_failure_does_not_replace_publish_exception(self) -> None:
        with patch.object(services.subprocess, "run", side_effect=subprocess.TimeoutExpired("docker", 40)):
            with self.assertRaisesRegex(RuntimeError, "publish failed"):
                try:
                    raise RuntimeError("publish failed")
                finally:
                    services._cleanup_command(["docker", "stop", "owned-id"], "SearXNG")


if __name__ == "__main__":
    unittest.main()

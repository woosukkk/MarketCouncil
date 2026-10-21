"""Packaged daily entry points and resources; never register or run a real job."""
import json
import os
import queue
os.environ.setdefault("OPENAI_API_KEY", "test-key")
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from desktop import daily_official as daily
from desktop import main as desktop
from desktop.preferences import VERSION


class PackagedDailyTests(unittest.TestCase):
    def test_frozen_command_uses_the_distributed_executable(self) -> None:
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", r"C:\Apps\MarketCouncil\MarketCouncil.exe"):
            self.assertEqual(daily.launch_command(), [sys.executable, "--daily-official"])
            self.assertEqual(daily.launch_command(setup=True), [sys.executable, "--daily-setup"])
            command = daily.install_command()
            self.assertEqual(command[-2:], ["-ExecutablePath", str(Path(sys.executable).resolve())])
            self.assertEqual(Path(command[5]), daily.BUNDLE / "tools" / "install_daily_official.ps1")

    def test_source_commands_keep_existing_python_launcher(self) -> None:
        with patch.object(sys, "frozen", False, create=True):
            expected = [str(daily.ROOT / "venv" / "Scripts" / "pythonw.exe"), "-m", "desktop.daily_official"]
            self.assertEqual(daily.launch_command(), expected)
            self.assertEqual(daily.launch_command(setup=True), [*expected, "--setup"])
            self.assertNotIn("-ExecutablePath", daily.install_command())

    def test_frozen_runtime_copies_only_service_resources_into_writable_data(self) -> None:
        from app import local_services
        before = Path.cwd()
        self.addCleanup(os.chdir, before)
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            bundle = base / "readonly-bundle"
            infra = bundle / "infra" / "searxng"
            infra.mkdir(parents=True)
            for name in ("docker-compose.yml", "settings.yml"):
                (infra / name).write_text(name, encoding="utf-8")
            data = base / "user-data" / "daily"
            with patch.object(daily, "DATA", data), patch.object(daily, "BUNDLE", bundle), patch.object(sys, "frozen", True, create=True), patch.dict(os.environ), patch.object(local_services, "PROJECT_ROOT"), patch.object(local_services, "COMPOSE_FILE"), patch.object(local_services, "SEARXNG_URL"):
                daily.prepare_runtime("http://127.0.0.1:8080")
                self.assertEqual(Path.cwd(), data.parent)
                self.assertEqual(local_services.PROJECT_ROOT, data.parent)
                self.assertEqual(local_services.COMPOSE_FILE, data.parent / "infra" / "searxng" / "docker-compose.yml")
                self.assertEqual(local_services.COMPOSE_FILE.read_text(), "docker-compose.yml")
                self.assertEqual(os.environ["HF_HOME"], str(data.parent / "models"))
                self.assertEqual(os.environ["PLAYWRIGHT_BROWSERS_PATH"], str(data.parent / "browser"))
                self.assertEqual(local_services.SEARXNG_URL, "http://127.0.0.1:8080")
            os.chdir(before)

    def test_browser_marker_is_written_only_after_successful_install(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.object(daily, "DATA", Path(folder) / "daily"), patch.object(sys, "frozen", True, create=True), patch.object(daily.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaisesRegex(RuntimeError, "browser-install.log"):
                daily.ensure_browser()
            self.assertFalse((Path(folder) / "browser-ready").exists())
            run.return_value.returncode = 0
            daily.ensure_browser()
            self.assertTrue((Path(folder) / "browser-ready").exists())
            self.assertEqual(run.call_args.args[0], [sys.executable, "--install-browser"])
            daily.ensure_browser()
            self.assertEqual(run.call_count, 2)

    def test_source_runtime_does_not_download_a_browser(self) -> None:
        with patch.object(sys, "frozen", False, create=True), patch.object(daily.subprocess, "run") as run:
            daily.ensure_browser()
        run.assert_not_called()

    def test_daily_entrypoint_never_opens_the_manual_analysis_window(self) -> None:
        with patch.object(sys, "argv", ["MarketCouncil.exe", "--daily-official"]), patch.object(daily, "run", return_value=1) as run, patch.object(desktop, "Desktop") as gui:
            with self.assertRaises(SystemExit) as error:
                desktop.main()
        self.assertEqual(error.exception.code, 1)
        run.assert_called_once_with()
        gui.assert_not_called()

    def test_setup_entrypoint_only_opens_explicit_setup(self) -> None:
        with patch.object(sys, "argv", ["MarketCouncil.exe", "--daily-setup"]), patch.object(daily, "setup") as setup, patch.object(daily, "run") as run, patch.object(desktop, "Desktop") as gui:
            desktop.main()
        setup.assert_called_once_with()
        run.assert_not_called()
        gui.assert_not_called()

    def test_readiness_setup_button_launches_only_settings(self) -> None:
        with patch.object(sys, "frozen", True, create=True), patch.object(desktop.subprocess, "Popen") as launch:
            desktop.Desktop.setup_daily(SimpleNamespace(busy=False))
        self.assertEqual(launch.call_args.args[0], [sys.executable, "--daily-setup"])

    def test_manual_analysis_callback_still_uses_existing_workflow_without_paid_calls(self) -> None:
        from app import local_services
        from app import debate_workflow
        from tools import analysis_debate_store, debate_transcript_renderer, run_metrics
        before = Path.cwd()
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / "browser-ready").touch()
            owner = SimpleNamespace(company=SimpleNamespace(get=lambda: "Example"), key=SimpleNamespace(get=lambda: "test-key"), dart=SimpleNamespace(get=lambda: ""), search=SimpleNamespace(get=lambda: "http://127.0.0.1:8080"), busy=False, matched_name="Example", company_choice=SimpleNamespace(current=lambda: 0), company_candidates=[{"name": "Example", "ticker": "EXAMPLE"}], loaded_settings=None, messages=queue.Queue(), task=lambda callback: callback())
            workflow = Mock()
            store = Mock()
            store.save.return_value = str(data / "saved-result.json")
            try:
                with patch.object(desktop, "DATA", data), patch.object(sys, "frozen", False, create=True), patch.dict(os.environ), patch.object(desktop.messagebox, "askyesno", return_value=True), patch.object(local_services, "ensure_local_services") as services, patch.object(local_services, "PROJECT_ROOT"), patch.object(local_services, "COMPOSE_FILE"), patch.object(local_services, "SEARXNG_URL"), patch.object(debate_workflow, "DebateWorkflow", return_value=workflow), patch.object(analysis_debate_store, "AnalysisDebateStore", return_value=store), patch.object(debate_transcript_renderer, "DebateTranscriptRenderer"), patch.object(run_metrics, "measure_analysis", side_effect=lambda company, callback, folder: callback()):
                    desktop.Desktop.run(owner)
                workflow.run.assert_called_once_with("Example")
                services.assert_called_once_with()
                self.assertEqual(owner.result_path, Path(store.save.return_value).resolve())
            finally:
                os.chdir(before)

    def test_busy_manual_analysis_does_not_launch_settings(self) -> None:
        with patch.object(desktop.subprocess, "Popen") as launch:
            desktop.Desktop.setup_daily(SimpleNamespace(busy=True))
        launch.assert_not_called()

    def test_frozen_diagnostics_do_not_require_git(self) -> None:
        with tempfile.TemporaryDirectory() as folder, patch.object(daily, "BUNDLE", Path(folder)), patch.object(sys, "frozen", True, create=True), patch.object(daily.subprocess, "run") as run:
            metadata = Path(folder) / "release-build.json"
            self.assertEqual(daily.source_version(), "unknown")
            metadata.write_text(json.dumps({"source_commit": "a" * 40, "version": VERSION}))
            self.assertEqual(daily.source_version(), "a" * 40)
            metadata.write_text(json.dumps({"source_commit": "invalid", "version": VERSION}))
            self.assertEqual(daily.source_version(), "unknown")
        run.assert_not_called()


class PackagedCheckpointTests(unittest.TestCase):
    @staticmethod
    def fake_workflow(owner) -> None:
        for attribute, method in [("evidence_workflow", "run"), ("historical_collector", "collect"), ("regime_workflow", "run"), ("bull_agent", "analyze_with_context"), ("bear_agent", "analyze_with_context"), ("sentiment_agent", "analyze"), ("video_agent", "run_latest_short_topics"), ("navigator_agent", "analyze")]:
            setattr(owner, attribute, SimpleNamespace(**{method: Mock(return_value={})}))
        owner.debate_agent = SimpleNamespace(**{name: Mock(return_value={}) for name in ("create_agenda", "bull_turn", "bear_turn", "moderator_review", "summarize")}, _build_graph=Mock(return_value="graph"))

    def test_frozen_checkpoint_uses_valid_build_identity_without_source_files(self) -> None:
        from app.recoverable_debate_workflow import RecoverableDebateWorkflow
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", folder, create=True), patch("app.recoverable_debate_workflow.DebateWorkflow.__init__", self.fake_workflow):
            root = Path(folder)
            metadata = root / "release-build.json"
            metadata.write_text(json.dumps({"source_commit": "a" * 40, "version": VERSION}))
            workflow = RecoverableDebateWorkflow(root / "checkpoint.json", "company", "day")
            workflow.evidence_workflow.run("company")
            RecoverableDebateWorkflow(root / "checkpoint.json", "company", "day")
            metadata.write_text(json.dumps({"source_commit": "b" * 40, "version": VERSION}))
            with self.assertRaisesRegex(ValueError, "scope"):
                RecoverableDebateWorkflow(root / "checkpoint.json", "company", "day")

    def test_frozen_missing_or_invalid_build_identity_fails_closed(self) -> None:
        from app.recoverable_debate_workflow import RecoverableDebateWorkflow
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", folder, create=True), patch("app.recoverable_debate_workflow.DebateWorkflow.__init__", self.fake_workflow):
            root = Path(folder)
            with self.assertRaises(FileNotFoundError):
                RecoverableDebateWorkflow(root / "checkpoint.json", "company", "day")
            for invalid in [{"source_commit": "a" * 7, "version": VERSION}, {"source_commit": "g" * 40, "version": VERSION}, {"source_commit": "a" * 40, "version": "999.0.0"}, [], {"version": VERSION}]:
                with self.subTest(metadata=invalid):
                    (root / "release-build.json").write_text(json.dumps(invalid))
                    with self.assertRaises(ValueError):
                        RecoverableDebateWorkflow(root / "checkpoint.json", "company", "day")


@unittest.skipUnless(os.name == "nt", "Windows scheduled-task command generation")
class InstallerCommandTests(unittest.TestCase):
    def test_installer_keeps_source_action_and_supports_frozen_action_without_registration(self) -> None:
        installer = daily.ROOT / "tools" / "install_daily_official.ps1"
        # Every scheduler cmdlet is replaced before the real script is evaluated.
        mocks = r'''
function New-ScheduledTaskAction { param($Execute,$Argument,$WorkingDirectory) [pscustomobject]@{Execute=$Execute;Argument=$Argument;WorkingDirectory=$WorkingDirectory} }
function New-ScheduledTaskTrigger { param([switch]$AtLogOn,[switch]$Daily,$User,$At) [pscustomobject]@{Delay=""} }
function New-ScheduledTaskPrincipal { param($UserId,$LogonType,$RunLevel) @{} }
function New-ScheduledTaskSettingsSet { param([switch]$StartWhenAvailable,$MultipleInstances,$ExecutionTimeLimit,[switch]$AllowStartIfOnBatteries,[switch]$DontStopIfGoingOnBatteries) @{} }
function Register-ScheduledTask { param($TaskName,$Action,$Trigger,$Principal,$Settings,$Description,[switch]$Force) $script:CapturedAction=$Action }
'''
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder) / "Market Council.exe"
            executable.touch()
            for frozen in (False, True):
                with self.subTest(frozen=frozen):
                    invocation = ". '" + str(installer).replace("'", "''") + "'"
                    if frozen:
                        invocation += " -ExecutablePath '" + str(executable).replace("'", "''") + "'"
                    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", mocks + "\n" + invocation + "\n$script:CapturedAction | ConvertTo-Json -Compress"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    action = json.loads(result.stdout)
                    if frozen:
                        self.assertEqual(Path(action["Execute"]).resolve(), executable.resolve())
                        self.assertEqual(action["Argument"], "--daily-official")
                        self.assertEqual(Path(action["WorkingDirectory"]).resolve(), Path(folder).resolve())
                    else:
                        self.assertEqual(action["Execute"], "powershell.exe")
                        self.assertIn("run_daily_official.ps1", action["Argument"])
                        self.assertEqual(action["WorkingDirectory"], str(daily.ROOT))


if __name__ == "__main__":
    unittest.main()

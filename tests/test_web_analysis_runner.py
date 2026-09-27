import subprocess
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch

from app.web_analysis_runner import AnalysisRunner, PROJECT_ROOT, run_analysis


class WebAnalysisRunnerTest(unittest.TestCase):
    def test_cli_result_and_errors(self) -> None:
        path = PROJECT_ROOT / "results" / "analysis_debate" / "test" / "analysis_debate_test.json"
        with patch("app.web_analysis_runner.subprocess.run") as run, patch.object(Path, "is_file", return_value=True):
            run.return_value = subprocess.CompletedProcess([], 0, f"토론 원본 JSON: {path}\n", "")
            self.assertEqual(run_analysis("삼성전자"), path.relative_to(PROJECT_ROOT))
            self.assertEqual(run.call_args.kwargs["input"], "삼성전자\n")
            self.assertEqual(run.call_args.kwargs["cwd"], PROJECT_ROOT)
            run.return_value = subprocess.CompletedProcess([], 1, "수집 실패", "")
            with self.assertRaisesRegex(RuntimeError, "수집 실패"):
                run_analysis("삼성전자")
            run.side_effect = subprocess.TimeoutExpired("analysis", 3600)
            with self.assertRaisesRegex(RuntimeError, "60분"):
                run_analysis("삼성전자")
        with self.assertRaises(ValueError):
            run_analysis("not-supported")

    def test_rejects_missing_or_unexpected_result(self) -> None:
        with patch("app.web_analysis_runner.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, "완료", "")
            with self.assertRaisesRegex(RuntimeError, "결과 경로"):
                run_analysis("삼성전자")
            run.return_value.stdout = f"토론 원본 JSON: {PROJECT_ROOT / 'README.md'}"
            with self.assertRaisesRegex(RuntimeError, "결과 파일"):
                run_analysis("삼성전자")

    def test_duplicate_job_is_rejected_and_retry_is_allowed(self) -> None:
        with patch("app.web_analysis_runner.ThreadPoolExecutor") as executor:
            future: Future[Path] = Future()
            executor.return_value.submit.return_value = future
            runner = AnalysisRunner()
            runner.start("삼성전자")
            with self.assertRaisesRegex(RuntimeError, "이미 분석"):
                runner.start("SK하이닉스")
            executor.return_value.submit.assert_called_once()
            future.set_exception(RuntimeError("failed"))
            runner.start("SK하이닉스")
            self.assertEqual(executor.return_value.submit.call_count, 2)
            self.assertEqual(runner.current()[0], "SK하이닉스")


if __name__ == "__main__":
    unittest.main()

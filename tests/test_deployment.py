import os
import unittest
from unittest.mock import patch

from app.admin_access import analysis_allowed
from app.web_analysis_runner import AnalysisRunner
from app.local_services import ensure_local_services
from rag.chroma_client import get_chroma_client


class DeploymentTest(unittest.TestCase):
    def test_public_access_fails_closed_before_job_submission(self) -> None:
        with patch.dict(os.environ, {"MARKETCOUNCIL_MODE": "public", "ADMIN_TOKEN": "x" * 32}):
            self.assertFalse(analysis_allowed())
            self.assertFalse(analysis_allowed("wrong"))
            self.assertTrue(analysis_allowed("x" * 32))
            with patch("app.web_analysis_runner.ThreadPoolExecutor") as pool:
                runner = AnalysisRunner()
                with self.assertRaises(RuntimeError):
                    runner.start("삼성전자")
                pool.return_value.submit.assert_not_called()
                runner.start("삼성전자", admin_token="x" * 32)
                pool.return_value.submit.assert_called_once()
        with patch.dict(os.environ, {"MARKETCOUNCIL_MODE": "public", "ADMIN_TOKEN": ""}):
            self.assertFalse(analysis_allowed())
        with patch.dict(os.environ, {"MARKETCOUNCIL_MODE": "invalid"}):
            self.assertFalse(analysis_allowed())

    def test_cloud_never_falls_back_to_local(self) -> None:
        with patch.dict(os.environ, {"CHROMA_MODE": "cloud", "CHROMA_API_KEY": ""}), patch(
            "rag.chroma_client.chromadb.PersistentClient"
        ) as local:
            with self.assertRaises(ValueError):
                get_chroma_client()
            local.assert_not_called()
        with patch.dict(os.environ, {"CHROMA_MODE": "cloud", "CHROMA_API_KEY": "test",
                                    "CHROMA_TENANT": "tenant", "CHROMA_DATABASE": "db"}), patch(
            "rag.chroma_client.chromadb.CloudClient"
        ) as cloud:
            self.assertIs(get_chroma_client(), cloud.return_value)
            cloud.assert_called_once_with(api_key="test", tenant="tenant", database="db")

    def test_managed_search_never_starts_docker(self) -> None:
        with patch.dict(os.environ, {"MANAGE_LOCAL_SERVICES": "false"}), patch(
            "app.local_services._service_ready", return_value=False
        ), patch("app.local_services._wait_until") as wait, patch(
            "app.local_services._docker_ready"
        ) as docker:
            ensure_local_services()
            wait.assert_called_once()
            docker.assert_not_called()

    def test_public_ui_does_not_create_runner(self) -> None:
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {"MARKETCOUNCIL_MODE": "public", "ADMIN_TOKEN": "x" * 32}), patch(
            "app.web_analysis_runner.AnalysisRunner"
        ) as runner, patch("app.debate_view_data.list_debate_files", return_value=[]):
            app = AppTest.from_file("streamlit_app.py", default_timeout=30).run()
            app.radio(key="workspace_page").set_value("새 분석").run()
            self.assertFalse(app.exception)
            self.assertFalse(any(button.key == "start_analysis" for button in app.button))
            runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()

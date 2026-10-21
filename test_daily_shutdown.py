import sys
import tempfile
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from desktop import daily_official as daily


class NotificationTests(unittest.TestCase):
    def test_notification_closes_without_a_click(self) -> None:
        window = Mock()
        window.mainloop.side_effect = lambda: window.after.call_args.args[1]()
        module = types.ModuleType("tkinter")
        module.Tk = Mock(return_value=window)
        module.ttk = types.SimpleNamespace(Label=Mock(), Button=Mock())
        with patch.dict(sys.modules, {"tkinter": module}):
            daily.notify("Completed")
        window.after.assert_called_once_with(8000, window.destroy)
        window.destroy.assert_called_once()

    def test_missing_gui_does_not_raise_after_publication(self) -> None:
        with patch.dict(sys.modules, {"tkinter": None}):
            daily.notify("Completed")

    def test_failed_notification_releases_its_window(self) -> None:
        window = Mock()
        window.mainloop.side_effect = RuntimeError("GUI unavailable")
        module = types.ModuleType("tkinter")
        module.Tk = Mock(return_value=window)
        module.ttk = types.SimpleNamespace(Label=Mock(), Button=Mock())
        with patch.dict(sys.modules, {"tkinter": module}):
            daily.notify("Completed")
        window.destroy.assert_called_once()


class DailyShutdownTests(unittest.TestCase):
    def setUp(self) -> None:
        self.context = ExitStack()
        self.addCleanup(self.context.close)
        folder = self.context.enter_context(tempfile.TemporaryDirectory())
        self.context.enter_context(patch.object(daily, "DATA", Path(folder)))
        self.context.enter_context(patch.object(daily, "credentials", return_value={}))
        self.context.enter_context(patch.object(daily, "source_version", return_value="test"))
        self.resources = Mock()
        self.context.enter_context(patch.object(daily, "ExitStack", return_value=self.resources))
        self.workflow = self.context.enter_context(patch.object(daily, "run_once", return_value="completed"))
        self.failure = self.context.enter_context(patch.object(daily, "save_failure"))
        self.notification = self.context.enter_context(patch.object(daily, "notify"))
        self.events = []
        self.resources.close.side_effect = lambda: self.events.append("cleanup")
        self.notification.side_effect = lambda message: self.events.append("notification")

    def test_success_releases_resources_before_notification(self) -> None:
        self.assertEqual(daily.run(), 0)
        self.assertEqual(self.events[:2], ["cleanup", "notification"])
        self.failure.assert_not_called()

    def test_failure_releases_resources_and_keeps_original_error(self) -> None:
        original = RuntimeError("analysis failed")
        self.workflow.side_effect = original
        self.assertEqual(daily.run(), 1)
        self.assertEqual(self.events[:2], ["cleanup", "notification"])
        self.assertIs(self.failure.call_args.args[1], original)

    def test_cleanup_failure_does_not_invalidate_successful_publication(self) -> None:
        self.resources.close.side_effect = [RuntimeError("cleanup failed"), None]
        self.assertEqual(daily.run(), 0)
        self.assertEqual(self.failure.call_args.args[0], "cleanup")
        self.notification.assert_called_once()

    def test_cleanup_failure_does_not_mask_original_failure(self) -> None:
        original = RuntimeError("analysis failed")
        self.workflow.side_effect = original
        self.resources.close.side_effect = [RuntimeError("cleanup failed"), None]
        self.assertEqual(daily.run(), 1)
        self.assertEqual(self.failure.call_args_list[0].args[0], "cleanup")
        self.assertIs(self.failure.call_args_list[-1].args[1], original)

    def test_already_published_has_no_completion_popup(self) -> None:
        self.workflow.side_effect = daily.AlreadyPublished()
        self.assertEqual(daily.run(), 0)
        self.notification.assert_not_called()
        self.failure.assert_not_called()


if __name__ == "__main__":
    unittest.main()

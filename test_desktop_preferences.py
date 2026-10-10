import tempfile
import unittest
from pathlib import Path
from desktop.preferences import load_preferences, save_preferences, newer_release

class PreferencesTest(unittest.TestCase):
    def test_remembers_inputs_without_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"preferences.json"
            self.assertEqual(load_preferences(path),{})
            save_preferences(path,"삼성전자","http://localhost:8080")
            self.assertEqual(load_preferences(path)["company"],"삼성전자")
            path.write_text('{"key":"secret","company":"삼성전자"}',encoding="utf-8")
            self.assertEqual(load_preferences(path),{"company":"삼성전자"})
            path.write_text('[]',encoding="utf-8")
            self.assertEqual(load_preferences(path),{})
    def test_only_new_desktop_releases(self):
        releases=[{"tag_name":"web-v99.0.0"},{"tag_name":"desktop-v0.4.1"},{"tag_name":"desktop-v0.5.0","draft":True},{"tag_name":"desktop-vbad"}]
        self.assertEqual(newer_release(releases)["tag_name"],"desktop-v0.4.1")
        self.assertIsNone(newer_release([{"tag_name":"desktop-v0.3.0"}]))

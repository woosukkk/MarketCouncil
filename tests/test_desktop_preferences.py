import tempfile
import unittest
from pathlib import Path
from desktop.preferences import VERSION, load_preferences, save_preferences, newer_release

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
        major,minor,patch=map(int,VERSION.split("."))
        next_tag=f"desktop-v{major}.{minor}.{patch+1}"
        releases=[{"tag_name":"web-v99.0.0"},{"tag_name":next_tag},{"tag_name":f"desktop-v{major+1}.0.0","draft":True},{"tag_name":"desktop-vbad"},{"tag_name":"desktop-v"+VERSION}]
        self.assertEqual(newer_release(releases)["tag_name"],next_tag)
        self.assertIsNone(newer_release([{"tag_name":"desktop-v0.3.0"}]))

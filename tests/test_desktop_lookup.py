import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from desktop.main import Desktop

class LookupButtonTests(unittest.TestCase):
    def test_lookup_keeps_typed_name_and_reaches_search_without_tk(self) -> None:
        owner=SimpleNamespace(busy=False,company=Mock(),company_choice=Mock(),messages=queue.Queue(),task=Mock())
        owner.company.get.return_value="Apple"
        with patch("desktop.preferences.load_preferences") as preferences:
            Desktop.lookup_company(owner)
        preferences.assert_not_called()
        owner.company.delete.assert_not_called()
        owner.task.assert_called_once()
        candidates=[{"name":"Apple","ticker":"AAPL","exchange":"NASDAQ"}]
        with patch("tools.company_lookup.find_companies",return_value=candidates) as search:
            owner.task.call_args.args[0]()
        search.assert_called_once_with("Apple")
        self.assertEqual(owner.messages.get(),("companies",("Apple",candidates)))

if __name__=="__main__":unittest.main()

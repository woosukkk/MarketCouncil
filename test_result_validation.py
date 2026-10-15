"""The same contract cases run in the web importer and the desktop importer."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from desktop.cloud import upload_result
from tools.result_validation import validate_result


class ResultValidationTests(unittest.TestCase):
    def test_shared_contract_cases(self) -> None:
        fixture=json.loads((Path(__file__).parent / "frontend/tests/result-validation-cases.json").read_text(encoding="utf-8"))
        for row in fixture["cases"]:
            with self.subTest(row["name"]):
                value=row.get("result", {**copy.deepcopy(fixture["base"]), **row.get("fields", {})})
                if row["valid"]:
                    self.assertIs(validate_result(value), value)
                else:
                    with self.assertRaises(ValueError):
                        validate_result(value)

    def test_bad_or_oversized_result_never_reaches_network(self) -> None:
        session={"user":{"id":"owner"},"access_token":"unused"}
        for result in [{"company_name":"Example","rounds":[],"agenda":[None]}, {"company_name":"Example","rounds":[],"bull_analysis":"x"*2000000}]:
            with self.subTest(keys=list(result)), patch("desktop.cloud.request") as api:
                with self.assertRaises(ValueError):
                    upload_result(result, session, "11111111-1111-4111-8111-111111111111")
                api.assert_not_called()

    def test_nullable_metadata_uses_safe_upload_defaults(self) -> None:
        with patch("desktop.cloud.request", side_effect=[[],[{"id":"saved"}]]) as api:
            upload_result({"company_name":"Example","rounds":[],"financial_data":None,"created_at":None}, {"user":{"id":"owner"},"access_token":"unused"}, "11111111-1111-4111-8111-111111111111")
            row=api.call_args.args[1]
            self.assertEqual(row["ticker"], "")
            self.assertIsInstance(row["analysis_date"], str)

    def test_render_collections_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            validate_result({"company_name":"Example","rounds":[{}]*1001})


if __name__ == "__main__":
    unittest.main()

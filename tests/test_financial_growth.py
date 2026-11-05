import unittest
from unittest.mock import Mock, patch
import pandas as pd
from tools.financial_data import calculate_growth, operating_income_change, get_financial_data

class GrowthTests(unittest.TestCase):
    def test_positive_baseline_and_unusable_values(self) -> None:
        self.assertEqual(calculate_growth(120, 100), 20)
        for current, previous in [(100,-100),(100,0),(None,100),(100,None),(float("nan"),100),(100,float("inf"))]:
            self.assertIsNone(calculate_growth(current,previous))

    def test_profit_transitions_and_absolute_changes(self) -> None:
        for current, previous, status, delta in [(100,-100,"흑자전환",200),(-200,-100,"적자확대",-100),(-50,-100,"적자축소",50),(-100,100,"적자전환",-200),(0,-100,"손익분기 전환",100)]:
            with self.subTest(status=status):
                result=operating_income_change(current,previous)
                self.assertEqual(result["status"],status)
                self.assertEqual(result["absolute_change"],delta)
                self.assertIsNone(result["growth_pct"])
        self.assertEqual(operating_income_change(120,100)["growth_pct"],20)
        self.assertEqual(operating_income_change(None,100)["status"],"확인 불가")

    def test_financial_output_explains_loss_to_profit_to_both_agents(self) -> None:
        company=Mock()
        company.financials=pd.DataFrame({"2026":[120,100],"2025":[100,-100]},index=["Total Revenue","Operating Income"])
        company.cashflow=company.balance_sheet=pd.DataFrame()
        with patch("tools.financial_data.yf.Ticker",return_value=company),patch("tools.financial_data.get_latest_price",return_value=(10,"2026-10-15")),patch("tools.financial_data._get_market_cap",return_value=1000):
            result=get_financial_data("삼성전자")
        self.assertIn("흑자전환",result["operating_income_growth"])
        self.assertNotIn("-200%",result["operating_income_growth"])
        self.assertEqual(result["operating_income_change"]["absolute_change"],200)

if __name__=="__main__":unittest.main()

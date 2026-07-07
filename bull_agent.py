user_prompt = f"""
다음 기업을 Bull 관점에서 분석해줘.

기업명: {company_name}
티커: {financial_data["ticker"]}
현재 주가: {financial_data["current_price"]}

최근 연간 매출: {financial_data["current_revenue"]}
전년도 매출: {financial_data["previous_revenue"]}
매출 성장률: {financial_data["revenue_growth"]}

최근 연간 영업이익: {financial_data["current_operating_income"]}
전년도 영업이익: {financial_data["previous_operating_income"]}
영업이익 성장률: {financial_data["operating_income_growth"]}

제공된 금융 데이터만 근거로 긍정적인 투자 요인과
성장 가능성을 분석해줘.

수치가 없는 항목은 억지로 해석하지 마.
"""
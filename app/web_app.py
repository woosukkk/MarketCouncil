import os
import re
from html import escape
from typing import Any

import streamlit as st


PAGE_CSS = """
<style>
:root {
  --ink: #111713;
  --muted: #626a64;
  --paper: #eef1ed;
  --panel: #f9faf7;
  --line: #cbd1cb;
  --accent: #173f30;
  --signal: #c9f36a;
  --bear: #d97854;
}
.stApp { background: linear-gradient(90deg, rgba(17,23,19,.035) 1px, transparent 1px), var(--paper); background-size: 6.25rem 100%; color: var(--ink); }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1240px; padding: 1.25rem 2.5rem 5rem; }
h1, h2, h3 { color: var(--ink); font-family: "Arial Narrow", "Aptos Display", "Segoe UI", sans-serif; letter-spacing: -.045em; }
h1 { font-size: clamp(3rem, 7vw, 6.4rem); line-height: .84; margin: 4rem 0 1.25rem; max-width: 720px; }
p, label, .stMarkdown { color: var(--ink); }
.masthead { align-items: center; border-bottom: 1px solid var(--ink); display: flex; font-family: ui-monospace, "Cascadia Code", monospace; font-size: .7rem; justify-content: space-between; letter-spacing: .08em; padding: .65rem 0; text-transform: uppercase; }
.masthead strong { font-size: .78rem; letter-spacing: -.02em; }
.live { align-items: center; display: flex; gap: .5rem; }
.live::before { background: var(--signal); border: 1px solid var(--ink); border-radius: 50%; content: ""; height: .55rem; width: .55rem; }
.eyebrow { color: var(--accent); font-family: ui-monospace, "Cascadia Code", monospace; font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.lede { color: var(--muted); font-size: clamp(1rem, 2vw, 1.22rem); line-height: 1.55; max-width: 650px; margin: 0 0 2.75rem; }
.brief { border-bottom: 1px solid var(--line); border-top: 1px solid var(--line); display: grid; grid-template-columns: 1.15fr repeat(3, 1fr); margin: 0 0 2rem; }
.brief > div { border-right: 1px solid var(--line); min-height: 7.25rem; padding: 1rem 1.1rem; }
.brief > div:last-child { border-right: 0; }
.brief .brief-title { background: var(--accent); color: white; }
.brief small { color: var(--muted); display: block; font-family: ui-monospace, "Cascadia Code", monospace; font-size: .68rem; letter-spacing: .08em; margin-bottom: 1.35rem; text-transform: uppercase; }
.brief-title small { color: rgba(255,255,255,.62); }
.brief strong { display: block; font-size: .95rem; line-height: 1.35; }
.rule { border-top: 1px solid var(--ink); margin: 2.25rem 0; }
.metric-strip { background: var(--panel); border-bottom: 1px solid var(--ink); border-top: 1px solid var(--ink); display: grid; grid-template-columns: 1.5fr repeat(3, 1fr); margin: 1.25rem 0 1rem; }
.metric { border-right: 1px solid var(--line); padding: 1rem 1.1rem; }
.metric:last-child { border-right: 0; }
.metric span { color: var(--muted); display: block; font-family: ui-monospace, "Cascadia Code", monospace; font-size: .68rem; letter-spacing: .07em; margin-bottom: .55rem; text-transform: uppercase; }
.metric strong { font-size: 1.22rem; font-weight: 650; }
.thesis-rail { background: var(--panel); border-bottom: 1px solid var(--line); display: grid; grid-template-columns: var(--bull) var(--bear); height: .65rem; margin-bottom: 2.5rem; position: relative; }
.thesis-rail .bull { background: var(--signal); }
.thesis-rail .bear { background: var(--bear); }
.thesis-rail::after { background: var(--ink); content: ""; height: 1.25rem; left: 50%; position: absolute; top: -.3rem; width: 1px; }
div[data-testid="stForm"] { background: var(--panel); border: 1px solid var(--ink); border-radius: 0; box-shadow: 8px 8px 0 rgba(23,63,48,.12); padding: 1.15rem; }
.stButton > button, .stFormSubmitButton > button { background: var(--accent); border: 1px solid var(--accent); border-radius: 0; color: white; min-height: 3.1rem; font-weight: 700; letter-spacing: .02em; }
.stButton > button:hover, .stFormSubmitButton > button:hover { background: var(--ink); border-color: var(--ink); color: var(--signal); }
.stButton > button:focus-visible, .stFormSubmitButton > button:focus-visible, input:focus-visible { outline: 3px solid var(--signal) !important; outline-offset: 2px; }
div[data-baseweb="input"] > div { background: white; border-radius: 0; }
[data-testid="stAlert"] { border-radius: 0; }
.report-meta { align-items: end; display: flex; justify-content: space-between; }
.report-meta h2 { margin-bottom: 0; }
@media (prefers-reduced-motion: no-preference) {
  .brief, div[data-testid="stForm"] { animation: reveal .35s ease-out both; }
  @keyframes reveal { from { opacity: 0; transform: translateY(8px); } }
}
@media (max-width: 760px) {
  .block-container { padding: .75rem 1rem 4rem; }
  h1 { margin-top: 2.75rem; }
  .masthead span:nth-child(2) { display: none; }
  .brief { grid-template-columns: 1fr 1fr; }
  .brief > div { border-bottom: 1px solid var(--line); min-height: 6.5rem; }
  .brief > div:nth-child(2) { border-right: 0; }
  .brief > div:nth-child(n+3) { border-bottom: 0; }
  .metric-strip { grid-template-columns: 1fr 1fr; }
  .metric:nth-child(2) { border-right: 0; }
  .metric:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
}
</style>
"""


def validate_company_name(value: str) -> str:
    company_name = value.strip()
    if len(company_name) < 2:
        raise ValueError("기업명을 두 글자 이상 입력해 주세요.")
    if len(company_name) > 80:
        raise ValueError("기업명은 80자 이하로 입력해 주세요.")
    return company_name


def extract_metrics(judge_result: str) -> dict[str, str]:
    def value(label: str, default: str) -> str:
        match = re.search(
            rf"(?im)^-?\s*{re.escape(label)}\s*:\s*(.+)$",
            judge_result,
        )
        return match.group(1).strip() if match else default

    return {
        "rating": value("Final Rating", "확인 불가"),
        "bull": value("Bull Score", "—"),
        "bear": value("Bear Score", "—"),
        "confidence": value("Confidence", "확인 불가"),
    }


def score_split(bull_score: str, bear_score: str) -> tuple[int, int]:
    try:
        bull = max(0, float(bull_score))
        bear = max(0, float(bear_score))
    except ValueError:
        return 50, 50
    total = bull + bear
    if total == 0:
        return 50, 50
    bull_percent = round(bull / total * 100)
    return bull_percent, 100 - bull_percent


@st.cache_resource(show_spinner=False)
def _judge_agent() -> Any:
    from agents.judge_agent import JudgeAgent

    return JudgeAgent()


def run_analysis(company_name: str, use_debate: bool) -> tuple[dict, str]:
    from tools.markdown_report_renderer import MarkdownReportRenderer

    result = _judge_agent().analyze(
        company_name,
        debate_mode="new" if use_debate else "none",
    )
    markdown = MarkdownReportRenderer().render(result)
    return result, markdown


def _metric_strip(metrics: dict[str, str]) -> None:
    safe_metrics = {key: escape(value) for key, value in metrics.items()}
    bull_percent, bear_percent = score_split(metrics["bull"], metrics["bear"])
    st.markdown(
        '<div class="metric-strip">'
        f'<div class="metric"><span>Final rating</span><strong>{safe_metrics["rating"]}</strong></div>'
        f'<div class="metric"><span>Bull case</span><strong>{safe_metrics["bull"]}</strong></div>'
        f'<div class="metric"><span>Bear case</span><strong>{safe_metrics["bear"]}</strong></div>'
        f'<div class="metric"><span>Confidence</span><strong>{safe_metrics["confidence"]}</strong></div>'
        '</div>'
        f'<div class="thesis-rail" style="--bull:{bull_percent}%;--bear:{bear_percent}%" '
        'aria-label="Bull and bear score comparison">'
        '<div class="bull"></div><div class="bear"></div></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="MarketCouncil",
        page_icon="◫",
        layout="wide",
    )
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="masthead"><strong>MarketCouncil / Research desk</strong>'
        '<span>Facts → Expectations → Hypotheses</span>'
        '<span class="live">Engine ready</span></div>',
        unsafe_allow_html=True,
    )
    st.title("Investment research,\nunder cross-examination.")
    st.markdown(
        '<p class="lede">한 기업을 낙관과 반대 가설로 동시에 검토합니다. 예측을 포장하기보다 '
        '확인된 사실, 근거의 한계, 판단이 바뀌는 조건을 한 장의 리서치 기록으로 남깁니다.</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<section class="brief">'
        '<div class="brief-title"><small>Research protocol</small><strong>결론보다 검증 가능한 근거를 먼저 봅니다.</strong></div>'
        '<div><small>01 / Evidence</small><strong>사실과 시장 기대를 분리</strong></div>'
        '<div><small>02 / Contest</small><strong>Bull·Bear 가설을 같은 기준으로 비교</strong></div>'
        '<div><small>03 / Revision</small><strong>강화·약화·폐기 조건을 명시</strong></div>'
        '</section>',
        unsafe_allow_html=True,
    )

    if not os.getenv("OPENAI_API_KEY"):
        st.error("OPENAI_API_KEY가 설정되지 않았습니다.")
        st.stop()

    with st.form("analysis_request"):
        company_input = st.text_input(
            "분석 기업",
            placeholder="예: 삼성전자",
        )
        use_debate = st.toggle(
            "쟁점이 남으면 토론 실행",
            value=False,
            help="정밀도는 높아질 수 있지만 처리 시간과 API 사용량이 증가합니다.",
        )
        submitted = st.form_submit_button("분석 시작", use_container_width=True)

    if not submitted:
        st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
        st.caption("RESEARCH WINDOW  ·  향후 1–4주     EVIDENCE ORDER  ·  공시 → 금융 데이터 → 최신 자료")
        return

    try:
        company_name = validate_company_name(company_input)
        with st.status(f"{company_name} 근거를 수집하고 있습니다.", expanded=True) as status:
            st.write("금융 데이터와 공식 자료 확인")
            result, markdown = run_analysis(company_name, use_debate)
            status.update(label="분석이 완료됐습니다.", state="complete", expanded=False)
    except Exception as error:
        st.error(f"분석을 완료하지 못했습니다: {error}")
        return

    st.markdown('<div class="rule"></div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="report-meta"><div><div class="eyebrow">{escape(company_name)} · 1–4 week view</div>'
        '<h2>판단 원장</h2></div><div class="eyebrow">Evidence-linked report</div></div>',
        unsafe_allow_html=True,
    )
    _metric_strip(extract_metrics(str(result.get("judge_result", ""))))
    st.markdown(markdown)
    st.download_button(
        "Markdown 보고서 다운로드",
        data=markdown,
        file_name=f"{company_name}_analysis.md",
        mime="text/markdown",
    )


if __name__ == "__main__":
    main()

import json
import os
from pathlib import Path
from typing import Any

import altair as alt
import streamlit as st
import pandas as pd

from app.debate_view_data import (
    collect_evidence,
    find_issue_turn,
    issue_status,
    list_debate_files,
    load_debate,
    navigation_issue,
    ordered_agenda,
    round_change,
)
from tools.debate_transcript_renderer import DebateTranscriptRenderer
from app.web_analysis_runner import AnalysisRunner, TICKER_MAP
from app.admin_access import analysis_allowed


st.set_page_config(
    page_title="MarketCouncil · 투자 토론",
    page_icon=":material/forum:",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.html(Path(__file__).parent / "app" / "debate_ui.css")

STATUS_LABELS = {
    "OPEN": "논의 대기",
    "CONTESTED": "견해 대립",
    "RESOLVED": "쟁점 해소",
    "STALEMATE": "반복·교착",
    "UNKNOWN": "자료 부족",
}


@st.cache_data(show_spinner=False, max_entries=8)
def cached_load(path_text: str, modified_at: float) -> dict[str, Any]:
    del modified_at
    return load_debate(Path(path_text))


@st.cache_resource
def analysis_runner() -> AnalysisRunner:
    return AnalysisRunner()


@st.fragment(run_every="2s")
def show_analysis_launcher() -> None:
    if os.getenv("MARKETCOUNCIL_MODE") == "viewer":
        st.info("저장된 분석 결과를 열람하는 데모입니다. 새 분석 실행은 제공하지 않습니다.")
        return
    token = ""
    if os.getenv("MARKETCOUNCIL_MODE", "local") != "local":
        token = st.text_input("관리자 실행 키", type="password", key="admin_token")
        if not analysis_allowed(token):
            st.info("토론 결과는 누구나 볼 수 있습니다. 새 분석은 관리자만 실행할 수 있습니다.")
            return
    runner = analysis_runner()
    company, future = runner.current()
    running = future is not None and not future.done()
    with st.container(key="launcher"):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            with st.container(width="stretch"):
                st.markdown("### MarketCouncil")
                st.caption("근거로 읽는 투자 토론")
            selected_company = st.selectbox(
                "새로 분석할 기업", list(TICKER_MAP), key="analysis_company", disabled=running,
                width=220,
            )
            if st.button(
                "분석 시작", key="start_analysis", type="primary",
                icon=":material/play_arrow:", disabled=running,
            ):
                try:
                    runner.start(selected_company, admin_token=token) if token else runner.start(selected_company)
                except (RuntimeError, ValueError) as error:
                    st.error(str(error))
                else:
                    st.rerun()
        st.caption("새 분석은 OpenAI API를 사용하며 수 분 이상 걸릴 수 있습니다.")
        if running:
            st.status(f"{company} 분석 진행 중 · 완료되면 새 결과가 자동으로 열립니다.", state="running")
            st.caption("기존 토론은 계속 볼 수 있습니다. 분석 중에는 웹 서버를 종료하지 마세요.")
        elif future is not None:
            try:
                result_path = future.result()
            except Exception as error:
                st.error(f"{company} 분석 실패")
                with st.expander("실패 원인", expanded=True):
                    st.text(str(error))
            else:
                st.success(f"{company} 분석 완료 · 결과가 저장되었습니다.")
                if st.session_state.get("opened_analysis") is not future:
                    st.session_state.opened_analysis = future
                    st.session_state.pending_debate_session = result_path
                    st.rerun()


def evidence_ids(turn: dict[str, Any], evidence: dict[str, dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for value in turn.get("evidence", []):
        if isinstance(value, dict) and value.get("evidence_id"):
            ids.append(str(value["evidence_id"]))
        elif not isinstance(value, dict):
            match = next(
                (key for key, item in evidence.items() if item.get("reason") == str(value)),
                "",
            )
            if match:
                ids.append(match)
    return ids


def show_position(
    title: str,
    turn: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    key_prefix: str,
) -> None:
    with st.container(key=f"position_{key_prefix}"):
        is_bull = title.startswith("Bull")
        st.badge(title, icon=":material/trending_up:" if is_bull else ":material/trending_down:",
                 color="green" if is_bull else "red")
        st.markdown("#### 핵심 주장")
        st.write(turn.get("claim") or "확인 불가")
        with st.expander("반론과 논리 읽기"):
            for field, label in (
                ("target_claim", "반박 대상"), ("response", "직접 반론"),
                ("warrant", "근거 → 주장 연결 논리"), ("qualifier", "성립 조건·한계"),
                ("concession", "인정한 부분"), ("missing_evidence", "부족한 근거"),
            ):
                st.markdown(f"**{label}**")
                st.write(turn.get(field) or "확인 불가")

        ids = evidence_ids(turn, evidence)
        if ids:
            st.markdown("**사용 근거**")
            for index, evidence_id in enumerate(ids):
                item = evidence.get(evidence_id, {})
                source_type = {
                    "official_report": "공식 보고서", "official": "공식 자료",
                    "regulatory_filing": "공시", "news": "뉴스", "report": "리포트",
                    "financial_data": "금융 데이터", "web": "웹 자료",
                }.get(str(item.get("source_type", "")), item.get("source_type") or "출처 유형 확인 불가")
                verification = "인용 대조 완료" if item.get("verified") else "인용 확인 필요"
                selected = st.session_state.get("selected_evidence_id") == evidence_id
                with st.container(key=f"evidence_row_{key_prefix}_{index}_{'selected' if selected else 'idle'}"):
                    st.button(
                        str(item.get("title") or "출처명 확인 불가"),
                        key=f"{key_prefix}_{index}_{evidence_id}",
                        icon=":material/description:", type="tertiary", width="stretch",
                        on_click=select_evidence, args=(evidence_id,),
                    )
                    st.caption(f"{source_type} · {item.get('published_at') or '발행일 확인 불가'} · {verification} · {evidence_id}")


def select_evidence(evidence_id: str) -> None:
    st.session_state.selected_evidence_id = evidence_id
    st.session_state.evidence_filter = "전체"


def open_article(path: str, issue_id: str) -> None:
    st.session_state.article_path = path
    st.session_state[f"issue_{path}"] = issue_id


def close_article() -> None:
    st.session_state.pop("article_path", None)


def show_evidence(item: dict[str, Any]) -> None:
    if not item:
        st.info("가운데 원문의 근거 버튼을 선택하세요.", icon=":material/touch_app:")
        return
    evidence_id = str(item.get("evidence_id", "근거"))
    st.subheader(evidence_id)
    st.badge("인용 대조 완료" if item.get("verified") else "인용 확인 필요",
             color="green" if item.get("verified") else "orange")
    st.caption("인용 대조는 원문 연결 여부이며, 투자 가설의 사실성을 보증하지 않습니다.")
    if item.get("title"):
        st.write(item["title"])
    if item.get("page_number"):
        st.caption(f"PDF {item['page_number']}페이지")
    st.caption(f"출처 유형: {item.get('source_type') or '확인 불가'} · 발행일: {item.get('published_at') or '확인 불가'}")
    st.markdown("**정확 인용**")
    st.info(item.get("exact_quote") or "확인 불가")
    with st.expander("인용 문단 전체"):
        st.write(item.get("context_text") or "확인 불가")
    if item.get("reason"):
        st.markdown("**이 근거를 사용한 이유**")
        st.write(item["reason"])
    source_url = str(item.get("source_page_url") or item.get("source_url", ""))
    if source_url:
        st.link_button(
            "외부 원문 열기",
            source_url,
            icon=":material/open_in_new:",
            width="stretch",
        )


def show_regime_view(
    analysis: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
) -> None:
    if not analysis.get("regimes"):
        st.info("이 결과에는 시장 국면 비교 데이터가 없습니다.")
        for limitation in analysis.get("limitations", []):
            st.caption(limitation)
        return

    bull = analysis["regimes"]["past_bull"]
    bear = analysis["regimes"]["recent_bear"]

    display_series = analysis.get("display_series", {})
    series_options = {
        "최근 60거래일 · 일별": display_series.get("recent_daily", []),
        "최근 1년 · 월별": display_series.get("medium_monthly", []),
        "과거 · 분기별": display_series.get("historical_quarterly", []),
    }
    available_options = {
        label: rows for label, rows in series_options.items() if rows
    }
    if available_options:
        st.subheader("3년 시계열 흐름")
        selected_label = st.segmented_control(
            "표시 구간",
            list(available_options),
            default=next(iter(available_options)),
            key="regime_series_granularity",
        )
        selected_rows = available_options.get(selected_label, [])
        series_frame = pd.DataFrame(selected_rows)
        if not series_frame.empty:
            group_key = next(
                key for key, label in (
                    ("recent_daily", "최근 60거래일 · 일별"),
                    ("medium_monthly", "최근 1년 · 월별"),
                    ("historical_quarterly", "과거 · 분기별"),
                )
                if label == selected_label
            )
            period_evidence = analysis.get("timeline_evidence", {}).get(group_key, {})
            series_frame["evidence_ids"] = series_frame["period"].map(
                lambda period: ", ".join(
                    str(item.get("evidence_id", ""))
                    for item in period_evidence.get(str(period), [])
                    if item.get("evidence_id")
                ) or "확인된 주요 사건 없음"
            )
            series_frame["date"] = pd.to_datetime(series_frame["end_date"])
            selected_return = (
                series_frame.iloc[-1]["close"] / series_frame.iloc[0]["open"] - 1
            ) * 100
            drawdown = (
                series_frame["close"].div(series_frame["close"].cummax()).sub(1).min()
                * 100
            )
            benchmark_return = _compounded_return(
                series_frame["benchmark_return_pct"]
            )
            with st.container(horizontal=True):
                st.metric(
                    "현재 종가",
                    f"{series_frame.iloc[-1]['close']:,.2f}",
                    border=True,
                    chart_data=series_frame["close"].tolist(),
                    chart_type="line",
                )
                st.metric("선택 구간 수익률", f"{selected_return:+.2f}%", border=True)
                st.metric("선택 구간 최대 낙폭", f"{drawdown:.2f}%", border=True)
                st.metric(
                    "시장 대비",
                    (
                        f"{selected_return - benchmark_return:+.2f}%"
                        if benchmark_return is not None
                        else "확인 불가"
                    ),
                    border=True,
                )

            st.altair_chart(
                _regime_price_chart(series_frame, bull, bear),
                width="stretch",
                key=f"regime_price_{selected_label}",
            )
            display_columns = {
                "period": "기간",
                "start_date": "시작일",
                "end_date": "종료일",
                "open": "시가",
                "high": "고가",
                "low": "저가",
                "close": "종가",
                "return_pct": "수익률(%)",
                "max_drawdown_pct": "최대 낙폭(%)",
                "annualized_volatility_pct": "연환산 변동성(%)",
                "average_volume": "평균 거래량",
                "benchmark_return_pct": "시장 수익률(%)",
                "excess_return_pct": "시장 대비(%)",
                "evidence_ids": "기간 근거",
            }
            with st.expander("시계열 상세 데이터", icon=":material/table_chart:"):
                st.dataframe(
                    series_frame.rename(columns=display_columns)[
                        list(display_columns.values())
                    ],
                    column_config={
                        "수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "최대 낙폭(%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "연환산 변동성(%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "시장 수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "시장 대비(%)": st.column_config.NumberColumn(format="%.2f%%"),
                        "평균 거래량": st.column_config.NumberColumn(format="localized"),
                    },
                    hide_index=True,
                    width="stretch",
                )
            evidenced_periods = [
                str(period) for period in series_frame["period"]
                if period_evidence.get(str(period))
            ]
            if evidenced_periods:
                st.markdown("**표의 기간별 근거 원문**")
                for period in evidenced_periods:
                    items = period_evidence[period]
                    with st.expander(
                        f"{period} · 근거 {len(items)}개",
                        icon=":material/event_note:",
                    ):
                        for item in items:
                            st.markdown(
                                f"**{item.get('published_at', '날짜 확인 불가')} · "
                                f"{item.get('evidence_id', '')} · "
                                f"{item.get('title', '제목 확인 불가')}**"
                            )
                            show_evidence(item)

    st.subheader("시장 국면 비교")
    st.caption(analysis.get("methodology", {}).get("description", ""))
    period_columns = st.columns(2)
    with period_columns[0]:
        st.metric(
            "과거 상승 구간",
            f"{bull['metrics']['cumulative_return_pct']:+.2f}%",
            border=True,
        )
        st.caption(f"{bull['start_date']} ~ {bull['end_date']}")
    with period_columns[1]:
        st.metric(
            "최근 하락 구간",
            f"{bear['metrics']['cumulative_return_pct']:+.2f}%",
            border=True,
        )
        st.caption(f"{bear['start_date']} ~ {bear['end_date']}")

    comparison_rows = [
        {
            "비교 항목": row.get("metric", ""),
            "과거 상승장": _metric_text(row.get("past_bull"), row.get("unit", "")),
            "최근 하락장": _metric_text(row.get("recent_bear"), row.get("unit", "")),
            "변화": _metric_text(row.get("change"), row.get("unit", "")),
        }
        for row in analysis.get("comparison", [])
    ]
    st.dataframe(comparison_rows, hide_index=True, width="stretch")

    reasons = analysis.get("reasons", {})
    bull_reasons = reasons.get("past_bull", [])
    bear_reasons = reasons.get("recent_bear", [])
    reason_rows = []
    for index in range(max(len(bull_reasons), len(bear_reasons), 2)):
        bull_reason = bull_reasons[index] if index < len(bull_reasons) else {}
        bear_reason = bear_reasons[index] if index < len(bear_reasons) else {}
        reason_rows.append({
            "순위": index + 1,
            "과거 상승장의 이유": bull_reason.get("claim", "추가 데이터 필요"),
            "상승 근거": _reason_evidence_ids(bull_reason),
            "최근 하락장의 이유": bear_reason.get("claim", "추가 데이터 필요"),
            "하락 근거": _reason_evidence_ids(bear_reason),
        })
    st.subheader("상승·하락 이유 비교")
    st.dataframe(reason_rows, hide_index=True, width="stretch")

    regime_evidence = {
        key: item for key, item in evidence.items() if key.startswith("RE-")
    }
    main, source = st.columns([2.3, 1.2], gap="large")
    with main:
        event_rows = []
        for regime_id, regime_reasons in reasons.items():
            label = "과거 상승장" if regime_id == "past_bull" else "최근 하락장"
            for reason in regime_reasons:
                for item in reason.get("evidence", []):
                    event_rows.append({
                        "날짜": item.get("event_date", ""),
                        "국면": label,
                        "사건·해석": reason.get("claim", ""),
                        "분류": reason.get("classification", ""),
                        "1일 반응": _metric_text(item.get("price_reaction_1d_pct"), "%"),
                        "5일 반응": _metric_text(item.get("price_reaction_5d_pct"), "%"),
                        "시장조정 5일": _metric_text(item.get("market_adjusted_5d_pct"), "%"),
                        "근거": item.get("evidence_id", ""),
                    })
        st.subheader("사건과 가격 반응")
        if event_rows:
            st.dataframe(event_rows, hide_index=True, width="stretch")
        else:
            st.info("기간 안에서 검증된 사건 근거를 찾지 못했습니다.")
    with source:
        st.subheader("국면 근거 원문")
        if regime_evidence:
            selected = st.selectbox("근거 선택", list(regime_evidence), key="regime_evidence")
            show_evidence(regime_evidence[selected])
        else:
            st.info("표에 연결된 검증 근거가 없습니다.")

    for limitation in analysis.get("limitations", []):
        st.warning(limitation, icon=":material/warning:")


def _regime_price_chart(
    frame: pd.DataFrame,
    bull: dict[str, Any],
    bear: dict[str, Any],
) -> alt.VConcatChart:
    rising = "datum.open <= datum.close"
    colors = alt.condition(rising, alt.value("#16a34a"), alt.value("#dc2626"))
    base = alt.Chart(frame)
    regime_frame = pd.DataFrame([
        {
            "start": pd.to_datetime(bull["start_date"]),
            "end": pd.to_datetime(bull["end_date"]),
            "regime": "과거 상승장",
        },
        {
            "start": pd.to_datetime(bear["start_date"]),
            "end": pd.to_datetime(bear["end_date"]),
            "regime": "최근 하락장",
        },
    ])
    backgrounds = (
        alt.Chart(regime_frame)
        .mark_rect(opacity=0.08)
        .encode(
            x=alt.X("start:T"),
            x2="end:T",
            color=alt.Color(
                "regime:N",
                scale=alt.Scale(
                    domain=["과거 상승장", "최근 하락장"],
                    range=["#16a34a", "#dc2626"],
                ),
                legend=alt.Legend(title="선택 국면", orient="top"),
            ),
        )
    )
    wicks = base.mark_rule().encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("low:Q", title="가격", scale=alt.Scale(zero=False)),
        y2="high:Q",
        color=colors,
    )
    candles = base.mark_bar(size=8).encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("open:Q", title="가격", scale=alt.Scale(zero=False)),
        y2="close:Q",
        color=colors,
        tooltip=[
            alt.Tooltip("period:N", title="기간"),
            alt.Tooltip("open:Q", title="시가", format=",.2f"),
            alt.Tooltip("high:Q", title="고가", format=",.2f"),
            alt.Tooltip("low:Q", title="저가", format=",.2f"),
            alt.Tooltip("close:Q", title="종가", format=",.2f"),
            alt.Tooltip("return_pct:Q", title="수익률", format="+.2f"),
        ],
    )
    price = (backgrounds + wicks + candles).properties(height=360)
    volume = base.mark_bar().encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("average_volume:Q", title="거래량"),
        color=colors,
        tooltip=[
            alt.Tooltip("period:N", title="기간"),
            alt.Tooltip("average_volume:Q", title="거래량", format=","),
        ],
    ).properties(height=100)
    zoom = alt.selection_interval(
        name="regime_zoom",
        bind="scales",
        encodings=["x"],
    )
    return (
        alt.vconcat(price.add_params(zoom), volume, spacing=8)
        .resolve_scale(x="shared")
        .configure_view(stroke=None)
        .configure_axis(gridColor="#94a3b8", gridOpacity=0.1, labelColor="#64748b", titleColor="#64748b")
    )


def _compounded_return(values: pd.Series) -> float | None:
    valid = pd.to_numeric(values, errors="coerce").dropna()
    if valid.empty:
        return None
    return float(((valid.div(100).add(1)).prod() - 1) * 100)


def _metric_text(value: Any, unit: str) -> str:
    if value is None:
        return "확인 불가"
    prefix = "+" if isinstance(value, (int, float)) and value > 0 and unit == "%" else ""
    return f"{prefix}{value}{unit}"


def _reason_evidence_ids(reason: dict[str, Any]) -> str:
    values = [str(item.get("evidence_id", "")) for item in reason.get("evidence", [])]
    return ", ".join(value for value in values if value) or "확인 불가"


files = list_debate_files()
pending_session = st.session_state.pop("pending_debate_session", None)
if pending_session in files:
    st.session_state.debate_session = pending_session
    st.session_state.view_mode = "토론 탐색"
    st.session_state.workspace_page = "토론 보기"
with st.sidebar:
    st.title("MarketCouncil")
    st.caption("근거를 읽고, 경쟁 가설을 비교하세요.")
    workspace_page = st.radio(
        "페이지", ["토론 보기", "새 분석"], key="workspace_page",
    )
    st.caption("새 분석 메뉴에서 기업을 선택하고 토론을 시작하세요.")

if workspace_page == "새 분석":
    st.title("새 투자 분석")
    st.caption("기업을 선택하면 근거 수집부터 Bull/Bear 토론까지 실행합니다.")
    show_analysis_launcher()
    st.stop()

with st.sidebar:
    if not files:
        st.info("저장된 토론이 없습니다.")
    else:
        selected_path = st.selectbox(
            "저장된 세션", files,
            format_func=lambda path: f"{path.parent.name} · {path.stem.removeprefix('analysis_debate_')}",
            key="debate_session",
        )

if not files:
    st.title("첫 번째 투자 토론을 기다리고 있습니다")
    st.info("왼쪽 새 분석 메뉴에서 첫 토론을 시작하세요.")
    st.stop()

try:
    debate = cached_load(str(selected_path), selected_path.stat().st_mtime)
except (ValueError, OSError) as error:
    st.error(str(error))
    st.stop()

agenda = ordered_agenda(debate)
rounds = debate.get("rounds", [])
evidence = collect_evidence(debate)
summary = debate.get("moderator_summary", {})
company_name = str(debate.get("company_name", "기업명 확인 불가"))
st.title(f"{company_name} · 투자 토론")
price_date = debate.get("financial_data", {}).get("financial_facts", {}).get("price_date")
st.caption(
    f"분석 생성: {debate.get('created_at') or '확인 불가'}  ·  "
    f"가격 기준일: {price_date or '확인 불가'}  ·  저장된 분석"
)
with st.container(horizontal=True, horizontal_alignment="distribute", key="stat_strip"):
    st.markdown(f"핵심 의제 **{len(agenda)}개**")
    st.markdown(f"토론 **{len(rounds)}라운드**")
    st.markdown(f"인용 대조 **{sum(bool(item.get('verified')) for item in evidence.values())} / {len(evidence)}**")
    unresolved = f"{len(summary.get('unresolved_issues', []))}개" if "unresolved_issues" in summary else "확인 불가"
    st.markdown(f"미해결 **{unresolved}**")

st.session_state.setdefault("view_mode", "토론 탐색")
view_mode = st.segmented_control(
    "분석 보기", ["토론 탐색", "시장 국면", "최종 정리"],
    key="view_mode", width="stretch",
) or "토론 탐색"

if view_mode == "시장 국면":
    show_regime_view(debate.get("regime_analysis", {}), evidence)
    st.download_button(
        "시장 국면 JSON 내려받기",
        json.dumps(debate.get("regime_analysis", {}), ensure_ascii=False, indent=2),
        file_name=f"regime_{selected_path.stem}.json", mime="application/json",
        icon=":material/download:",
    )
elif view_mode == "최종 정리":
    st.subheader("토론이 남긴 결론")
    st.write(summary.get("summary") or "추가 데이터 필요")
    for field, label, icon in (
        ("agreements", "양측 합의점", ":material/handshake:"),
        ("unresolved_issues", "아직 풀리지 않은 쟁점", ":material/forum:"),
        ("required_evidence", "다음 판단에 필요한 근거", ":material/search:"),
    ):
        with st.container(border=True):
            st.subheader(label)
            for value in summary.get(field, []):
                st.markdown(f"{icon} {value}")
            if not summary.get(field):
                st.caption("기록된 항목 없음")
    st.caption(f"토론 종료 사유: {debate.get('stop_reason') or '확인 불가'}")
    st.caption("가설의 성립 조건·한계는 토론 탐색의 각 입장 카드에서 확인할 수 있습니다.")
else:
    overview = str(summary.get("summary") or debate.get("navigation", {}).get("overview") or "추가 데이터 필요")
    headline = str(summary.get("headline") or (agenda[0].get("title") if agenda else None) or "투자 토론 요약")
    lead = str(summary.get("lead") or overview)
    if agenda and rounds and st.session_state.get("article_path") != str(selected_path):
        st.subheader("토론 한눈에 보기")
        main_story, other_stories = st.columns([2.2, 1], gap="medium")
        with main_story:
            with st.container(key="conclusion_focus"):
                st.caption("주요 분석" if summary.get("headline") else "저장된 토론 · 기존 의제 순서")
                st.header(headline)
                st.write(lead)
                status = issue_status(debate, str(agenda[0].get("issue_id", "")))
                st.badge(STATUS_LABELS.get(status, status), color="blue")
                st.button("토론 읽기", key="featured_article", type="primary",
                          icon=":material/arrow_forward:", on_click=open_article,
                          args=(str(selected_path), str(agenda[0].get("issue_id", ""))))
        with other_stories:
            st.caption("함께 살펴볼 의제")
            for index, item in enumerate(agenda[1:], 1):
                with st.container(key=f"summary_article_{index}"):
                    st.subheader(str(item.get("title") or "의제 제목 확인 불가"))
                    st.write(item.get("question") or "추가 데이터 필요")
                    st.button("쟁점 읽기", key=f"article_{index}", on_click=open_article,
                              args=(str(selected_path), str(item.get("issue_id", ""))))
            if len(agenda) == 1:
                st.caption("이번 분석은 하나의 의제를 다룹니다.")
        st.caption("토론에서 정리한 분석입니다. 출처 원문과 근거의 한계는 상세에서 확인하세요.")
        st.stop()

    if agenda and rounds:
        st.button("기사 목록으로", icon=":material/arrow_back:", on_click=close_article, key="back_to_articles")
        article_issue = next((item for item in agenda if str(item.get("issue_id", "")) ==
                              st.session_state.get(f"issue_{selected_path}")), agenda[0])
        if article_issue is not agenda[0]:
            headline = str(article_issue.get("title") or "의제 제목 확인 불가")
            lead = str(navigation_issue(debate, str(article_issue.get("issue_id", ""))).get("core_disagreement")
                       or article_issue.get("question") or "추가 데이터 필요")
    with st.container(key="conclusion_focus"):
        st.header(headline)
        st.write(lead)
    st.caption(f"토론 종료 사유: {debate.get('stop_reason') or '확인 불가'}")

    if not agenda or not rounds:
        st.info("토론 의제 또는 라운드가 없습니다. 최종 정리와 시장 국면을 확인하세요.")
    else:
        with st.container(key="agenda_section"):
            st.subheader("토론 의제")
            issue_ids = [str(item.get("issue_id", "")) for item in agenda]
            with st.container(key="agenda_picker"):
                selected_issue_id = st.radio(
                    "의제 선택", issue_ids,
                    format_func=lambda value: next(
                        str(item.get("title", value)) for item in agenda
                        if str(item.get("issue_id", "")) == value
                    ),
                    key=f"issue_{selected_path}", label_visibility="collapsed", horizontal=True,
                )
            selected_issue = next(item for item in agenda if str(item.get("issue_id", "")) == selected_issue_id)
            guide = navigation_issue(debate, selected_issue_id)
            status = issue_status(debate, selected_issue_id)
            with st.container(horizontal=True, vertical_alignment="center"):
                st.badge(STATUS_LABELS.get(status, status), color={
                    "RESOLVED": "green", "CONTESTED": "orange", "OPEN": "blue",
                }.get(status, "gray"))
                st.caption("최종 쟁점 상태")
            if guide.get("core_disagreement"):
                with st.expander("핵심 대립 읽기"):
                    st.write(guide["core_disagreement"])

        center, right = st.columns([3, 1], gap="medium")
        with center:
            st.subheader("주장과 반론")
            st.caption(selected_issue.get("title", ""))
            with st.container(key="question_focus"):
                st.markdown("**이번 의제의 검증 질문**")
                st.write(selected_issue.get("question") or "확인 불가")
            round_options = [int(item.get("round", index)) for index, item in enumerate(rounds, 1)]
            number = st.segmented_control(
                "토론 진행", round_options, default=round_options[0],
                format_func=lambda value: f"{value}라운드",
                key=f"round_{selected_path}", width="stretch",
            ) or round_options[0]
            round_data = next(item for index, item in enumerate(rounds, 1) if int(item.get("round", index)) == number)
            scope = (str(selected_path), selected_issue_id, number)
            if st.session_state.get("evidence_scope") != scope:
                st.session_state.evidence_scope = scope
                st.session_state.pop("selected_evidence_id", None)
                st.session_state.evidence_filter = "전체"
            bull = find_issue_turn(round_data.get("bull_response", {}), selected_issue_id)
            bear = find_issue_turn(round_data.get("bear_response", {}), selected_issue_id)
            active_ids = evidence_ids(bull, evidence) + evidence_ids(bear, evidence)
            if st.session_state.get("selected_evidence_id") not in active_ids:
                st.session_state.selected_evidence_id = next(iter(active_ids), "")
            change = round_change(debate, selected_issue_id, number)
            if change:
                with st.container(key="round_changes"):
                    st.markdown("#### 이 라운드에서 달라진 점")
                    st.badge("새 근거", color="blue", icon=":material/add:")
                    new_ids = change.get("new_evidence_ids", [])
                    for new_id in new_ids:
                        st.write(f"{evidence.get(new_id, {}).get('title') or '출처명 확인 불가'} · {new_id}")
                    if not new_ids:
                        st.caption("기록된 새 근거 없음")
                    st.badge("인정한 부분", color="green", icon=":material/handshake:")
                    for concession in change.get("concessions", []):
                        st.write(concession)
                    if not change.get("concessions"):
                        st.caption("기록된 인정 사항 없음")
                    st.badge("남은 질문", color="orange", icon=":material/help:")
                    st.write(change.get("remaining_question") or "확인 불가")
                    with st.expander("양측 입장 변화 상세"):
                        st.markdown("**Bull 변화**")
                        st.write(change.get("bull_change") or "확인 불가")
                        st.markdown("**Bear 변화**")
                        st.write(change.get("bear_change") or "확인 불가")
            else:
                st.caption("이 라운드의 변화 요약은 기록되어 있지 않습니다.")
            bull_column, bear_column = st.columns(2, gap="medium")
            with bull_column:
                show_position("Bull · 상승 가설", bull, evidence, f"bull_{selected_issue_id}_{number}")
            with bear_column:
                show_position("Bear · 하락 가설", bear, evidence, f"bear_{selected_issue_id}_{number}")
            review = next((item for item in round_data.get("moderator_review", {}).get("issue_reviews", [])
                           if str(item.get("issue_id", "")) == selected_issue_id), {})
            with st.container(border=True):
                st.badge("Moderator · 라운드 검토", color="blue")
                st.write(review.get("assessment") or "검토 기록 없음")
                if review.get("status"):
                    st.caption(f"이 라운드의 상태: {STATUS_LABELS.get(review['status'], review['status'])}")

        with right:
            st.subheader("인용 근거")
            st.caption("선택한 의제·라운드에 연결된 원문")
            verification = st.selectbox(
                "인용 상태", ["전체", "인용 대조 완료", "인용 확인 필요"], key="evidence_filter",
            )
            active_ids = set(evidence_ids(bull, evidence) + evidence_ids(bear, evidence))
            filtered_evidence = {
                key: item for key, item in evidence.items() if key in active_ids and (
                    verification == "전체"
                    or (verification == "인용 대조 완료" and item.get("verified"))
                    or (verification == "인용 확인 필요" and not item.get("verified"))
                )
            }
            if filtered_evidence:
                if st.session_state.get("selected_evidence_id") not in filtered_evidence:
                    st.session_state.selected_evidence_id = next(iter(filtered_evidence))
                selected_evidence_id = st.selectbox(
                    "근거 선택", list(filtered_evidence), key="selected_evidence_id",
                )
                with st.container(key="evidence_panel"):
                    show_evidence(filtered_evidence[selected_evidence_id])
            else:
                st.info("이 의제·라운드에서 선택한 상태에 해당하는 인용 근거가 없습니다.")

with st.expander("분석 기록 내려받기", icon=":material/download:"):
    with st.container(horizontal=True):
        st.download_button(
            "JSON 원문", json.dumps(debate, ensure_ascii=False, indent=2),
            file_name=selected_path.name, mime="application/json",
        )
        st.download_button(
            "Markdown 기록", DebateTranscriptRenderer().render(debate),
            file_name=f"{selected_path.stem}.md", mime="text/markdown",
        )
st.caption("MarketCouncil · 사실, 시장 기대, 투자 가설을 구분하고 근거의 한계를 함께 읽습니다.")

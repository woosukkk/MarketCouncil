import json
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
    round_change,
)
from tools.debate_transcript_renderer import DebateTranscriptRenderer


st.set_page_config(
    page_title="MarketCouncil 토론",
    page_icon=":material/forum:",
    layout="wide",
)

STATUS_LABELS = {
    "OPEN": "논의 대기",
    "CONTESTED": "견해 대립",
    "RESOLVED": "쟁점 해소",
    "STALEMATE": "반복·교착",
    "UNKNOWN": "자료 부족",
}


@st.cache_data(show_spinner=False)
def cached_load(path_text: str, modified_at: float) -> dict[str, Any]:
    del modified_at
    return load_debate(Path(path_text))


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
    with st.container(border=True):
        st.subheader(title)
        st.markdown("**주장**")
        st.write(turn.get("claim") or "확인 불가")
        if turn.get("target_claim"):
            st.caption(f"반박 대상: {turn['target_claim']}")
        st.markdown("**직접 반론**")
        st.write(turn.get("response") or "확인 불가")
        if turn.get("warrant"):
            st.markdown("**근거 → 주장 연결 논리**")
            st.write(turn["warrant"])
        if turn.get("qualifier"):
            st.markdown("**성립 조건·한계**")
            st.write(turn["qualifier"])
        if turn.get("concession"):
            st.markdown("**인정한 부분**")
            st.write(turn["concession"])
        if turn.get("missing_evidence"):
            st.markdown("**부족한 근거**")
            st.write(turn["missing_evidence"])

        ids = evidence_ids(turn, evidence)
        if ids:
            st.markdown("**사용 근거**")
            for index, evidence_id in enumerate(ids):
                item = evidence.get(evidence_id, {})
                icon = ":material/verified:" if item.get("verified") else ":material/help:"
                if st.button(
                    evidence_id,
                    key=f"{key_prefix}_{index}_{evidence_id}",
                    icon=icon,
                    width="stretch",
                ):
                    st.session_state.selected_evidence_id = evidence_id


def show_evidence(item: dict[str, Any]) -> None:
    if not item:
        st.info("가운데 원문의 근거 버튼을 선택하세요.", icon=":material/touch_app:")
        return
    evidence_id = str(item.get("evidence_id", "근거"))
    st.subheader(evidence_id)
    st.caption("검증 완료" if item.get("verified") else "원문 검증 불가")
    if item.get("title"):
        st.write(item["title"])
    if item.get("page_number"):
        st.caption(f"PDF {item['page_number']}페이지")
    st.markdown("**정확 인용**")
    st.info(item.get("exact_quote") or "확인 불가")
    st.markdown("**인용 문단 전체**")
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
        .configure_axis(gridColor="#94a3b8", gridOpacity=0.15)
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
st.title("투자 토론 원문 뷰어")
st.caption("결론을 대신 내리지 않고 쟁점, 반론, 근거 원문을 읽기 쉽게 보여줍니다.")

if not files:
    st.info("저장된 토론이 없습니다. 먼저 run_marketcouncil.bat를 실행하세요.")
    st.stop()

with st.sidebar:
    st.header("토론 선택")
    selected_path = st.selectbox(
        "저장된 세션",
        files,
        format_func=lambda path: f"{path.parent.name} · {path.stem.removeprefix('analysis_debate_')}",
    )

debate = cached_load(str(selected_path), selected_path.stat().st_mtime)
agenda = debate.get("agenda", [])
rounds = debate.get("rounds", [])
evidence = collect_evidence(debate)

with st.sidebar:
    round_options = [int(item.get("round", index)) for index, item in enumerate(rounds, 1)]
    selected_rounds = st.pills(
        "라운드",
        round_options,
        default=round_options,
        selection_mode="multi",
    )
    verification = st.segmented_control(
        "근거 상태",
        ["전체", "검증 완료", "검증 불가"],
        default="전체",
    )

st.header(str(debate.get("company_name", "기업명 확인 불가")))
view_mode = st.segmented_control(
    "분석 보기",
    ["시장 국면 비교", "토론 원문"],
    default="시장 국면 비교" if debate.get("regime_analysis", {}).get("regimes") else "토론 원문",
    width="stretch",
)
if view_mode == "시장 국면 비교":
    show_regime_view(debate.get("regime_analysis", {}), evidence)
    st.download_button(
        "시장 국면 JSON 내려받기",
        json.dumps(debate.get("regime_analysis", {}), ensure_ascii=False, indent=2),
        file_name=f"regime_{selected_path.stem}.json",
        mime="application/json",
        icon=":material/download:",
        width="stretch",
    )
    st.stop()
metric_columns = st.columns(3)
metric_columns[0].metric("라운드", len(rounds))
metric_columns[1].metric("쟁점", len(agenda))
metric_columns[2].metric("검증 근거", sum(bool(item.get("verified")) for item in evidence.values()))

if not agenda:
    st.warning("이 토론에는 쟁점 정보가 없습니다.")
    st.stop()

issue_ids = [str(item.get("issue_id", "")) for item in agenda]
selected_issue_id = st.segmented_control(
    "쟁점 지도",
    issue_ids,
    default=issue_ids[0],
    format_func=lambda value: next(
        str(item.get("title", value)) for item in agenda
        if str(item.get("issue_id", "")) == value
    ),
    width="stretch",
)
selected_issue = next(
    item for item in agenda if str(item.get("issue_id", "")) == selected_issue_id
)
guide = navigation_issue(debate, selected_issue_id)

left, center, right = st.columns([1.1, 2.4, 1.5], gap="large")
with left:
    st.subheader("쟁점 안내")
    st.write(selected_issue.get("question") or "질문 확인 불가")
    status = issue_status(debate, selected_issue_id)
    st.caption(f"현재 상태: {STATUS_LABELS.get(status, status)}")
    st.markdown("**핵심 대립**")
    st.write(guide.get("core_disagreement") or "추가 안내 정보 없음")
    if guide.get("round_changes"):
        st.markdown("**라운드 변화**")
        for change in guide["round_changes"]:
            with st.expander(f"{change.get('round', '?')}라운드"):
                st.write(f"상승: {change.get('bull_change', '변화 없음')}")
                st.write(f"하락: {change.get('bear_change', '변화 없음')}")
                st.write(f"남은 질문: {change.get('remaining_question', '없음')}")

with center:
    st.subheader("논제별 토론 원문")
    visible_rounds = [item for item in rounds if int(item.get("round", 0)) in (selected_rounds or [])]
    for round_data in visible_rounds:
        number = int(round_data.get("round", 0))
        change = round_change(debate, selected_issue_id, number)
        with st.expander(f"{number}라운드", expanded=number == visible_rounds[0].get("round")):
            if change:
                st.info(
                    f"상승 변화: {change.get('bull_change', '')}\n\n"
                    f"하락 변화: {change.get('bear_change', '')}",
                    icon=":material/change_circle:",
                )
            bull = find_issue_turn(round_data.get("bull_response", {}), selected_issue_id)
            bear = find_issue_turn(round_data.get("bear_response", {}), selected_issue_id)
            bull_column, bear_column = st.columns(2, gap="medium")
            with bull_column:
                show_position("Bull 원문", bull, evidence, f"bull_{selected_issue_id}_{number}")
            with bear_column:
                show_position("Bear 원문", bear, evidence, f"bear_{selected_issue_id}_{number}")

with right:
    st.subheader("근거 원문")
    filtered_evidence = {
        key: item for key, item in evidence.items()
        if verification == "전체"
        or (verification == "검증 완료" and item.get("verified"))
        or (verification == "검증 불가" and not item.get("verified"))
    }
    current_id = st.session_state.get("selected_evidence_id", "")
    if current_id not in filtered_evidence:
        current_id = next(iter(filtered_evidence), "")
        st.session_state.selected_evidence_id = current_id
    if filtered_evidence:
        selected_evidence_id = st.selectbox(
            "근거 선택",
            list(filtered_evidence),
            index=list(filtered_evidence).index(current_id),
        )
        st.session_state.selected_evidence_id = selected_evidence_id
        show_evidence(filtered_evidence[selected_evidence_id])
    else:
        st.info("선택한 상태에 해당하는 근거가 없습니다.")

if debate.get("regime_analysis", {}).get("regimes"):
    st.divider()
    show_regime_view(debate["regime_analysis"], evidence)

st.divider()
download_json = json.dumps(debate, ensure_ascii=False, indent=2)
download_markdown = DebateTranscriptRenderer().render(debate)
download_columns = st.columns(2)
download_columns[0].download_button(
    "JSON 원문 내려받기",
    download_json,
    file_name=selected_path.name,
    mime="application/json",
    icon=":material/download:",
    width="stretch",
)
download_columns[1].download_button(
    "Markdown 기록 내려받기",
    download_markdown,
    file_name=f"{selected_path.stem}.md",
    mime="text/markdown",
    icon=":material/download:",
    width="stretch",
)

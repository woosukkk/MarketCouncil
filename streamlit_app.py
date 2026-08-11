import json
from pathlib import Path
from typing import Any

import streamlit as st

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
    st.markdown("**정확 인용**")
    st.info(item.get("exact_quote") or "확인 불가")
    st.markdown("**인용 문단 전체**")
    st.write(item.get("context_text") or "확인 불가")
    if item.get("reason"):
        st.markdown("**이 근거를 사용한 이유**")
        st.write(item["reason"])
    source_url = str(item.get("source_url", ""))
    if source_url:
        st.link_button(
            "외부 원문 열기",
            source_url,
            icon=":material/open_in_new:",
            width="stretch",
        )


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
    st.subheader("토론 원문")
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

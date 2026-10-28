from tools.run_metrics import measure_stage
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from agents.analysis_debate_prompt import (
    BEAR_ANALYSIS_DEBATE_PROMPT,
    BULL_ANALYSIS_DEBATE_PROMPT,
)
from agents.moderator_agent import ModeratorAgent
from config import MODEL_NAME, OPENAI_API_KEY
from tools.regime_context import build_regime_context
from tools.citation_quality import assess_issue_evidence
from tools.evidence_dates import parse_evidence_date
from tools.evidence_text import is_navigation_text
from tools.debate_payload import debate_payload
from tools.structured_response import structured_response, ensure_complete


PARTICIPANT_SCHEMA = {
    "type": "object",
    "properties": {
        "position_summary": {"type": "string"},
        "issues": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "issue_id": {"type": "string"},
                    "claim": {"type": "string"},
                    "target_claim": {"type": "string"},
                    "response": {"type": "string"},
                    "warrant": {"type": "string"},
                    "qualifier": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_id": {"type": "string"},
                                "quote_id": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": [
                                "source_id",
                                "quote_id",
                                "reason",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "example_or_data": {"type": "string"},
                    "concession": {"type": "string"},
                    "missing_evidence": {"type": "string"},
                },
                "required": [
                    "issue_id", "claim", "target_claim", "response",
                    "warrant", "qualifier", "evidence",
                    "example_or_data", "concession",
                    "missing_evidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["position_summary", "issues"],
    "additionalProperties": False,
}


class DebateState(TypedDict, total=False):
    debate_input: str
    analysis_as_of: str
    evidence_catalog: list[dict[str, Any]]
    financial_data: dict[str, Any]
    agenda: list[dict[str, Any]]
    current_round: int
    max_rounds: int
    rounds: list[dict[str, Any]]
    bull_response: dict[str, Any]
    bear_response: dict[str, Any]
    moderator_review: dict[str, Any]
    stop_reason: str
    moderator_summary: dict[str, Any]


class AnalysisDebateAgent:
    MIN_ROUNDS = 2
    DEFAULT_MAX_ROUNDS = 3

    def __init__(
        self,
        client: OpenAI | None = None,
        max_rounds: int = DEFAULT_MAX_ROUNDS,
    ) -> None:
        self.client = client or OpenAI(api_key=OPENAI_API_KEY)
        self.moderator = ModeratorAgent(self.client)
        self.max_rounds = min(max(max_rounds, self.MIN_ROUNDS), 3)
        self.graph = self._build_graph()

    def run(
        self,
        company_name: str,
        financial_data: dict[str, Any],
        bull_result: str,
        bear_result: str,
        sentiment_summary: dict[str, Any],
        evidence_catalog: list[dict[str, Any]],
        regime_analysis: dict[str, Any] | None = None,
        video_summary: dict[str, Any] | None = None,
        as_of_date: str | None = None,
    ) -> dict[str, Any]:
        day = parse_evidence_date(as_of_date) if as_of_date is not None else datetime.now(timezone(timedelta(hours=9))).date()
        if day is None:
            raise ValueError("분석 기준일을 명확한 날짜로 지정하세요.")
        analysis_as_of = day.isoformat()
        debate_input = self._build_input(
            company_name=company_name,
            financial_data=financial_data,
            bull_result=bull_result,
            bear_result=bear_result,
            sentiment_summary=sentiment_summary,
            evidence_catalog=evidence_catalog,
            regime_analysis=regime_analysis,
            video_summary=video_summary,
            analysis_as_of=analysis_as_of,
        )
        result = self.graph.invoke(
            {
                "debate_input": debate_input,
                "analysis_as_of": analysis_as_of,
                "evidence_catalog": evidence_catalog,
                "financial_data": financial_data,
                "current_round": 1,
                "max_rounds": self.max_rounds,
                "rounds": [],
            },
            {"recursion_limit": 20},
        )
        rounds = result.get("rounds", [])
        latest = rounds[-1] if rounds else {}
        return {
            "analysis_as_of": analysis_as_of,
            "agenda": result.get("agenda", []),
            "rounds": rounds,
            "issue_statuses": result.get("moderator_review", {}).get(
                "issue_reviews", []
            ),
            "stop_reason": result.get("stop_reason", ""),
            "moderator_summary": result.get("moderator_summary", {}),
            "bull_rebuttal": latest.get("bull_response", {}),
            "bear_rebuttal": latest.get("bear_response", {}),
        }

    @measure_stage("create_agenda")
    def create_agenda(self, state: DebateState) -> DebateState:
        print("\n[중재자 토론 의제 선정 시작]")
        result = self.moderator.create_agenda(state["debate_input"])
        print("[중재자 토론 의제 선정 완료]")
        return {"agenda": result.get("agenda", [])}

    @measure_stage("bull_turn")
    def bull_turn(self, state: DebateState) -> DebateState:
        round_number = state["current_round"]
        print(f"\n[토론 {round_number}라운드 상승 관점 발언 시작]")
        response = self._participant_response("bull", state)
        print(f"[토론 {round_number}라운드 상승 관점 발언 완료]")
        return {"bull_response": response}

    @measure_stage("bear_turn")
    def bear_turn(self, state: DebateState) -> DebateState:
        round_number = state["current_round"]
        print(f"\n[토론 {round_number}라운드 하락 관점 반론 시작]")
        response = self._participant_response("bear", state)
        print(f"[토론 {round_number}라운드 하락 관점 반론 완료]")
        return {"bear_response": response}

    @measure_stage("moderator_review")
    def moderator_review(self, state: DebateState) -> DebateState:
        round_number = state["current_round"]
        print(f"\n[중재자 {round_number}라운드 검토 시작]")
        review = self.moderator.review_round({
            "analysis_as_of": state.get("analysis_as_of"),
            "agenda": state.get("agenda", []),
            "round": round_number,
            "previous_rounds": state.get("rounds", []),
            "bull_response": state.get("bull_response", {}),
            "bear_response": state.get("bear_response", {}),
            "original_evidence_and_analysis": state["debate_input"],
            "evidence_catalog": state.get("evidence_catalog", []),
        })
        self._apply_quality_limits(review, state.get("bull_response", {}), state.get("bear_response", {}))
        rounds = [
            *state.get("rounds", []),
            {
                "round": round_number,
                "bull_response": state.get("bull_response", {}),
                "bear_response": state.get("bear_response", {}),
                "moderator_review": review,
            },
        ]
        print(f"[중재자 {round_number}라운드 검토 완료]")
        return {"rounds": rounds, "moderator_review": review}

    @staticmethod
    def _apply_quality_limits(review: dict[str, Any], *responses: dict[str, Any]) -> None:
        flagged: dict[str, set[str]] = {}
        for response in responses:
            for issue in response.get("issues", []):
                quality = issue.get("citation_quality", {})
                reasons = set(quality.get("warnings", [])) & {"number_not_in_quotes", "non_evidentiary_quote", "future_source", "invalid_numeric_format"}
                if quality.get("identity_status") in {"missing", "invalid"}:
                    reasons.add("citation_identity_requires_review")
                if reasons:
                    flagged.setdefault(str(issue.get("issue_id", "")), set()).update(reasons)
        for item in review.get("issue_reviews", []):
            reasons = flagged.get(str(item.get("issue_id", "")))
            if not reasons:
                continue
            item["model_status"] = item.get("status")
            item["status"] = "UNKNOWN"
            item["quality_review_required"] = sorted(reasons)
            item["question_for_bull"] = ""
            item["question_for_bear"] = ""
            note = f"{item.get('issue_id', '')}: 선택 인용의 수치·본문 또는 출처 확인이 필요합니다."
            missing = review.setdefault("missing_evidence", [])
            if note not in missing:
                missing.append(note)

    def prepare_next_round(self, state: DebateState) -> DebateState:
        return {
            "current_round": state["current_round"] + 1,
            "bull_response": {},
            "bear_response": {},
        }

    @measure_stage("summarize")
    def summarize(self, state: DebateState) -> DebateState:
        review = state.get("moderator_review", {})
        if state["current_round"] >= state["max_rounds"]:
            stop_reason = f"최대 {state['max_rounds']}라운드에 도달했습니다."
        elif safety_reason := self._continuation_block_reason(state):
            stop_reason = safety_reason
        else:
            stop_reason = str(review.get("reason", "중재자가 토론 종료를 결정했습니다."))
        print("\n[중재자 토론 최종 정리 시작]")
        summary = self.moderator.summarize({
            "analysis_as_of": state.get("analysis_as_of"),
            "agenda": state.get("agenda", []),
            "rounds": state.get("rounds", []),
            "final_issue_reviews": review.get("issue_reviews", []),
            "financial_data": state.get("financial_data", {}),
            "evidence_catalog": state.get("evidence_catalog", []),
            "stop_reason": stop_reason,
        })
        print("[중재자 토론 최종 정리 완료]")
        return {"stop_reason": stop_reason, "moderator_summary": summary}

    def route_after_review(
        self,
        state: DebateState,
    ) -> Literal["next_round", "summary"]:
        if state["current_round"] < self.MIN_ROUNDS:
            return "next_round"
        if state["current_round"] >= state["max_rounds"]:
            return "summary"
        if not state.get("moderator_review", {}).get(
            "continue_debate", False
        ):
            return "summary"
        return "summary" if self._continuation_block_reason(state) else "next_round"

    @classmethod
    def _continuation_block_reason(cls, state: DebateState) -> str | None:
        issue_reviews = state.get("moderator_review", {}).get("issue_reviews", [])
        if not any(
            issue.get("status") in {"OPEN", "CONTESTED"}
            for issue in issue_reviews
        ):
            return "계속 검토할 OPEN 또는 CONTESTED 쟁점이 없습니다."
        if not cls._has_new_information(state):
            return "이전 전체 라운드 대비 새로운 유효 인용이나 실질적인 논점 변화가 없습니다."
        return None

    @classmethod
    def _has_new_information(cls, state: DebateState) -> bool:
        rounds = state.get("rounds", [])
        if len(rounds) < 2:
            return True
        current_items = cls._debate_items(
            state.get("bull_response", {}), state.get("bear_response", {})
        )
        previous_items = set()
        for previous in rounds[:-1]:
            previous_items.update(cls._debate_items(
                previous.get("bull_response", {}), previous.get("bear_response", {})
            ))
        return bool(current_items - previous_items) or any(
            issue.get("material_change") is True
            and bool(str(issue.get("change_reason", "")).strip())
            for issue in state.get("moderator_review", {}).get("issue_reviews", [])
        )

    @staticmethod
    def _debate_items(*responses: dict[str, Any]) -> set[tuple[str, str, str]]:
        items: set[tuple[str, str, str]] = set()
        for response in responses:
            for issue in response.get("issues", []):
                issue_id = str(issue.get("issue_id", ""))
                for evidence in issue.get("evidence", []):
                    if isinstance(evidence, dict) and evidence.get("citation_valid") is True:
                        items.add((issue_id, str(evidence["source_id"]), str(evidence["quote_id"])))
        return items

    def _participant_response(
        self,
        role: Literal["bull", "bear"],
        state: DebateState,
    ) -> dict[str, Any]:
        role_label = "상승 관점" if role == "bull" else "하락 관점"
        review = state.get("moderator_review", {})
        payload = {
            "analysis_as_of": state.get("analysis_as_of"),
            "round": state["current_round"],
            "agenda": state.get("agenda", []),
            "previous_rounds": state.get("rounds", []),
            "moderator_questions": review.get("issue_reviews", []),
            "current_opponent_response": (
                state.get("bull_response", {}) if role == "bear" else {}
            ),
        }
        instructions = (
            BULL_ANALYSIS_DEBATE_PROMPT
            if role == "bull"
            else BEAR_ANALYSIS_DEBATE_PROMPT
        )
        try:
            result=structured_response(self.client,instructions,debate_payload(state["debate_input"],payload,state.get("evidence_catalog",[])),f"{role}_debate_turn",PARTICIPANT_SCHEMA)
            return self._validate_citations(result,state.get("evidence_catalog",[]),state.get("analysis_as_of"))
        except Exception as error:
            raise RuntimeError(f"{role_label} 토론 발언 생성에 실패했습니다") from error

    @staticmethod
    def _validate_citations(
        response: dict[str, Any], catalog: list[dict[str, Any]], as_of_date: str | None = None,
    ) -> dict[str, Any]:
        sources = {str(source.get("source_id", "")): source for source in catalog}
        quotes = {
            (source["source_id"], quote["quote_id"]): quote["text"]
            for source in catalog
            for quote in source.get("quotes", [])
            if source.get("source_id") and quote.get("quote_id") and quote.get("text")
        }
        cutoff = parse_evidence_date(as_of_date)
        warning_text = {
            "number_not_in_quotes": "핵심 수치를 직접 확인할 수 있는 인용문 추가 필요",
            "invalid_numeric_format": "원화 수치의 단위 순서와 표기 확인 필요",
            "non_evidentiary_quote": "메뉴·로고 대신 주장을 뒷받침하는 본문 인용 필요",
            "source_date_missing": "근거 자료의 게시일 확인 필요",
            "future_source": "분석 기준일 이후 자료를 제외하고 당시 확인 가능한 근거 추가 필요",
            "stale_forecast": "단기 전망의 기간에 맞는 최신 근거 추가 필요",
        }
        for issue in response.get("issues", []):
            quality = assess_issue_evidence(issue, catalog, as_of_date)
            valid, errors = [], []
            for evidence in issue.get("evidence", []):
                if not isinstance(evidence, dict):
                    errors.append({"error": "제공된 원문에서 인용 쌍을 확인할 수 없음"})
                    continue
                key = (evidence.get("source_id"), evidence.get("quote_id"))
                if key not in quotes:
                    errors.append({**evidence, "error": "제공된 원문에서 인용 쌍을 확인할 수 없음"})
                    continue
                if is_navigation_text(quotes[key]):
                    errors.append({**evidence, "error": "메뉴·로고·이동 링크는 주장 근거로 사용할 수 없음"})
                    continue
                published = parse_evidence_date(sources[str(key[0])].get("published_at") or sources[str(key[0])].get("published_date"))
                if cutoff is not None and published is not None and published > cutoff:
                    errors.append({**evidence, "error": "분석 기준일 이후에 게시된 자료"})
                    continue
                valid.append({**evidence, "citation_valid": True, "exact_quote": quotes[key]})
            issue["evidence"] = valid
            issue["citation_errors"] = errors
            issue["citation_quality"] = quality
            notes = [warning_text[code] for code in quality["warnings"] if code in warning_text]
            if quality["identity_status"] != "matched":
                notes.append("주장을 뒷받침하는 원문 인용 확인 필요")
            existing = issue.get("missing_evidence", "")
            existing = existing if isinstance(existing, str) else ""
            issue["missing_evidence"] = " / ".join([existing] + [note for note in notes if note not in existing]).strip(" / ")
        return response

    @staticmethod
    def _ensure_complete(response: Any) -> None:
        ensure_complete(response)

    def _build_graph(self):
        builder = StateGraph(DebateState)
        builder.add_node("create_agenda", self.create_agenda)
        builder.add_node("bull_turn", self.bull_turn)
        builder.add_node("bear_turn", self.bear_turn)
        builder.add_node("moderator_review", self.moderator_review)
        builder.add_node("next_round", self.prepare_next_round)
        builder.add_node("summary", self.summarize)

        builder.add_edge(START, "create_agenda")
        builder.add_edge("create_agenda", "bull_turn")
        builder.add_edge("bull_turn", "bear_turn")
        builder.add_edge("bear_turn", "moderator_review")
        builder.add_conditional_edges(
            "moderator_review",
            self.route_after_review,
            {"next_round": "next_round", "summary": "summary"},
        )
        builder.add_edge("next_round", "bull_turn")
        builder.add_edge("summary", END)
        return builder.compile()

    @staticmethod
    def _build_input(
        company_name: str,
        financial_data: dict[str, Any],
        bull_result: str,
        bear_result: str,
        sentiment_summary: dict[str, Any],
        evidence_catalog: list[dict[str, Any]],
        regime_analysis: dict[str, Any] | None,
        video_summary: dict[str, Any] | None,
        analysis_as_of: str | None = None,
    ) -> str:
        return f"""기업명: {company_name}
분석 기준일: {analysis_as_of or "확인 불가"} (주가일·재무 기준기간과 구분)

[공통 금융 데이터]
{json.dumps(financial_data, ensure_ascii=False, indent=2, default=str)}

[Bull 전체 분석]
{bull_result}

[Bear 전체 분석]
{bear_result}

[뉴스 민심 요약]
{json.dumps(sentiment_summary, ensure_ascii=False, indent=2)}

[검증 가능한 근거 카탈로그]
{json.dumps(evidence_catalog, ensure_ascii=False, indent=2, default=str)}

[시계열 시장 국면 비교]
{build_regime_context(regime_analysis) if regime_analysis else "추가 데이터 필요"}

[영상 관점별 요약]
{json.dumps(video_summary, ensure_ascii=False, indent=2) if video_summary else "사용하지 않음"}
"""

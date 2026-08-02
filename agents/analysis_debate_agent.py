import json
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from openai import OpenAI

from agents.analysis_debate_prompt import (
    BEAR_ANALYSIS_DEBATE_PROMPT,
    BULL_ANALYSIS_DEBATE_PROMPT,
)
from agents.moderator_agent import ModeratorAgent
from config import MODEL_NAME, OPENAI_API_KEY


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
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "example_or_data": {"type": "string"},
                    "concession": {"type": "string"},
                    "missing_evidence": {"type": "string"},
                },
                "required": [
                    "issue_id", "claim", "target_claim", "response",
                    "evidence", "example_or_data", "concession",
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
        video_summary: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        debate_input = self._build_input(
            company_name=company_name,
            financial_data=financial_data,
            bull_result=bull_result,
            bear_result=bear_result,
            sentiment_summary=sentiment_summary,
            video_summary=video_summary,
        )
        result = self.graph.invoke(
            {
                "debate_input": debate_input,
                "current_round": 1,
                "max_rounds": self.max_rounds,
                "rounds": [],
            },
            {"recursion_limit": 20},
        )
        rounds = result.get("rounds", [])
        latest = rounds[-1] if rounds else {}
        return {
            "agenda": result.get("agenda", []),
            "rounds": rounds,
            "issue_statuses": result.get("moderator_review", {}).get(
                "issue_reviews", []
            ),
            "stop_reason": result.get("stop_reason", ""),
            "moderator_summary": result.get("moderator_summary", {}),
            "bull_rebuttal": latest.get("bull_response", {}),
            "bear_rebuttal": latest.get("bear_response", {}),
            "included_in_judge": False,
        }

    def create_agenda(self, state: DebateState) -> DebateState:
        print("\n[중재자 토론 의제 선정 시작]")
        result = self.moderator.create_agenda(state["debate_input"])
        print("[중재자 토론 의제 선정 완료]")
        return {"agenda": result.get("agenda", [])}

    def bull_turn(self, state: DebateState) -> DebateState:
        round_number = state["current_round"]
        print(f"\n[토론 {round_number}라운드 상승 관점 발언 시작]")
        response = self._participant_response("bull", state)
        print(f"[토론 {round_number}라운드 상승 관점 발언 완료]")
        return {"bull_response": response}

    def bear_turn(self, state: DebateState) -> DebateState:
        round_number = state["current_round"]
        print(f"\n[토론 {round_number}라운드 하락 관점 반론 시작]")
        response = self._participant_response("bear", state)
        print(f"[토론 {round_number}라운드 하락 관점 반론 완료]")
        return {"bear_response": response}

    def moderator_review(self, state: DebateState) -> DebateState:
        round_number = state["current_round"]
        print(f"\n[중재자 {round_number}라운드 검토 시작]")
        review = self.moderator.review_round({
            "agenda": state.get("agenda", []),
            "round": round_number,
            "previous_rounds": state.get("rounds", []),
            "bull_response": state.get("bull_response", {}),
            "bear_response": state.get("bear_response", {}),
            "original_evidence_and_analysis": state["debate_input"],
        })
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

    def prepare_next_round(self, state: DebateState) -> DebateState:
        return {
            "current_round": state["current_round"] + 1,
            "bull_response": {},
            "bear_response": {},
        }

    def summarize(self, state: DebateState) -> DebateState:
        review = state.get("moderator_review", {})
        if state["current_round"] >= state["max_rounds"]:
            stop_reason = f"최대 {state['max_rounds']}라운드에 도달했습니다."
        else:
            stop_reason = str(review.get("reason", "중재자가 토론 종료를 결정했습니다."))
        print("\n[중재자 토론 최종 정리 시작]")
        summary = self.moderator.summarize({
            "agenda": state.get("agenda", []),
            "rounds": state.get("rounds", []),
            "final_issue_reviews": review.get("issue_reviews", []),
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
        if state.get("moderator_review", {}).get("continue_debate", False):
            return "next_round"
        return "summary"

    def _participant_response(
        self,
        role: Literal["bull", "bear"],
        state: DebateState,
    ) -> dict[str, Any]:
        role_label = "상승 관점" if role == "bull" else "하락 관점"
        review = state.get("moderator_review", {})
        payload = {
            "round": state["current_round"],
            "agenda": state.get("agenda", []),
            "previous_rounds": state.get("rounds", []),
            "moderator_questions": review.get("issue_reviews", []),
            "current_opponent_response": (
                state.get("bull_response", {}) if role == "bear" else {}
            ),
            "original_evidence_and_analysis": state["debate_input"],
        }
        instructions = (
            BULL_ANALYSIS_DEBATE_PROMPT
            if role == "bull"
            else BEAR_ANALYSIS_DEBATE_PROMPT
        )
        last_error: Exception | None = None
        for attempt in range(2):
            token_limit = 2000 * (attempt + 1)
            try:
                response = self.client.responses.create(
                    model=MODEL_NAME,
                    instructions=instructions,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": f"{role}_debate_turn",
                            "strict": True,
                            "schema": PARTICIPANT_SCHEMA,
                        }
                    },
                    input=json.dumps(payload, ensure_ascii=False, default=str),
                    reasoning={"effort": "minimal"},
                    max_output_tokens=token_limit,
                )
                self._ensure_complete(response)
                result = json.loads(response.output_text)
                if not isinstance(result, dict):
                    raise ValueError("응답이 JSON 객체가 아닙니다.")
                return result
            except (json.JSONDecodeError, ValueError) as error:
                last_error = error
                if attempt == 0:
                    print(
                        f"[WARN] {role_label} 토론 응답이 불완전하여 "
                        f"{token_limit * 2} 토큰으로 재시도합니다."
                    )
                    continue
            except Exception as error:
                raise RuntimeError(
                    f"{role_label} 토론 발언 생성에 실패했습니다: {error}"
                ) from error

        raise RuntimeError(
            f"{role_label} 토론 JSON 응답 생성에 실패했습니다: {last_error}"
        ) from last_error

    @staticmethod
    def _ensure_complete(response: Any) -> None:
        status = getattr(response, "status", "completed")
        if status == "completed":
            return
        details = getattr(response, "incomplete_details", None)
        usage = getattr(response, "usage", None)
        raise ValueError(
            f"응답 상태={status}, 상세={details}, 사용량={usage}"
        )

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
        video_summary: dict[str, Any] | None,
    ) -> str:
        return f"""기업명: {company_name}

[공통 금융 데이터]
{json.dumps(financial_data, ensure_ascii=False, indent=2, default=str)}

[Bull 전체 분석]
{bull_result}

[Bear 전체 분석]
{bear_result}

[뉴스 민심 요약]
{json.dumps(sentiment_summary, ensure_ascii=False, indent=2)}

[영상 관점별 요약]
{json.dumps(video_summary, ensure_ascii=False, indent=2) if video_summary else "사용하지 않음"}
"""

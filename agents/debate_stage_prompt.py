"""One fixed instruction text for every call that shares the debate input.

The model provider reuses a cached prompt only when the beginning of the request
is identical. Each debate call used to start with its own role instructions, so
the long shared evidence input was never reused across roles. This prompt keeps
every role's rules in the system instructions and selects the role after the
shared input instead.
"""
from agents.analysis_debate_prompt import BEAR_ANALYSIS_DEBATE_PROMPT, BULL_ANALYSIS_DEBATE_PROMPT
from agents.moderator_prompt import MODERATOR_AGENDA_PROMPT, MODERATOR_REVIEW_PROMPT

ROLE_PROMPTS = {
    "debate_agenda": MODERATOR_AGENDA_PROMPT,
    "bull_debate_turn": BULL_ANALYSIS_DEBATE_PROMPT,
    "bear_debate_turn": BEAR_ANALYSIS_DEBATE_PROMPT,
    "debate_review": MODERATOR_REVIEW_PROMPT,
}

DEBATE_STAGE_PROMPT = (
    "너는 MarketCouncil 토론 단계에서 한 가지 역할만 맡는다.\n"
    "아래에 역할별 지시가 있다. 입력의 [이번 호출의 역할]에 적힌 역할의 지시만 따르고, "
    "다른 역할의 지시는 무시한다. 다른 역할의 입장을 대신 쓰지 않는다. "
    "응답은 지정된 JSON 스키마로만 한다.\n"
    + "".join(f"\n===== 역할: {role} =====\n{prompt.strip()}\n" for role, prompt in ROLE_PROMPTS.items())
)

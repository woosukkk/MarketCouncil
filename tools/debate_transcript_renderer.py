import html
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class DebateTranscriptRenderer:
    STATUS_LABELS = {
        "OPEN": "답변 대기",
        "CONTESTED": "의견 대립",
        "RESOLVED": "쟁점 해소",
        "STALEMATE": "반복·교착",
        "UNKNOWN": "자료 부족",
    }

    def __init__(
        self,
        output_dir: Path = Path("results/debate"),
    ) -> None:
        self.output_dir = output_dir

    def save(self, debate: dict[str, Any]) -> str:
        company_name = str(debate.get("company_name", "company"))
        safe_company = re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            company_name,
        ).strip("_") or "company"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self.output_dir / f"{safe_company}_{timestamp}.md"
        path.write_text(self.render(debate), encoding="utf-8")
        return str(path)

    def render(self, debate: dict[str, Any]) -> str:
        company_name = self._safe(debate.get("company_name", ""))
        agenda = debate.get("agenda", [])
        rounds = debate.get("rounds", [])
        sections = [
            f"# {company_name} 투자 토론 기록",
            f"> 생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            (
                "이 문서는 투자 결론을 제시하지 않습니다. "
                "아래 토론과 근거를 바탕으로 사용자가 직접 판단합니다."
            ),
        ]

        for round_data in rounds:
            round_number = round_data.get("round", "")
            sections.append(f"## {round_number}라운드")
            bull = round_data.get("bull_response", {}) or {}
            bear = round_data.get("bear_response", {}) or {}
            review = round_data.get("moderator_review", {}) or {}
            reviews = review.get("issue_reviews", [])

            for index, issue in enumerate(agenda, 1):
                sections.append(
                    self._render_issue(index, issue, bull, bear, reviews)
                )

            sections.append(self._render_round_review(review))

        sections.append(self._render_evidence_cards(rounds))
        sections.append(
            self._render_debate_status(
                debate.get("moderator_summary", {}) or {},
                str(debate.get("stop_reason", "")),
            )
        )
        return "\n\n".join(section for section in sections if section).strip() + "\n"

    def _render_issue(
        self,
        index: int,
        agenda: dict[str, Any],
        bull: dict[str, Any],
        bear: dict[str, Any],
        reviews: list[dict[str, Any]],
    ) -> str:
        issue_id = str(agenda.get("issue_id", ""))
        bull_issue = self._find_issue(bull, issue_id)
        bear_issue = self._find_issue(bear, issue_id)
        review = next(
            (
                item for item in reviews
                if str(item.get("issue_id", "")) == issue_id
            ),
            {},
        )
        status = self.STATUS_LABELS.get(
            str(review.get("status", "")),
            str(review.get("status", "미평가")),
        )
        return "\n".join([
            f"### 논제 {index}. {self._safe(agenda.get('title', ''))}",
            f"> {self._safe(agenda.get('question', ''))}",
            "",
            "| 구분 | 상승 관점 원문 | 하락 관점 원문 |",
            "|---|---|---|",
            self._row("주장", bull_issue.get("claim"), bear_issue.get("claim")),
            self._row(
                "상대 주장",
                bull_issue.get("target_claim"),
                bear_issue.get("target_claim"),
            ),
            self._row("반론", bull_issue.get("response"), bear_issue.get("response")),
            self._row(
                "근거",
                self._evidence_links(bull_issue.get("evidence", [])),
                self._evidence_links(bear_issue.get("evidence", [])),
            ),
            self._row(
                "사례·수치",
                bull_issue.get("example_or_data"),
                bear_issue.get("example_or_data"),
            ),
            self._row(
                "인정 사항",
                bull_issue.get("concession"),
                bear_issue.get("concession"),
            ),
            self._row(
                "부족한 근거",
                bull_issue.get("missing_evidence"),
                bear_issue.get("missing_evidence"),
            ),
            "",
            f"**중재 상태:** {self._safe(status)}",
            "",
            f"**중재 평가:** {self._safe(review.get('assessment', ''))}",
            "",
            f"**상승 관점 다음 질문:** {self._safe(review.get('question_for_bull', ''))}",
            "",
            f"**하락 관점 다음 질문:** {self._safe(review.get('question_for_bear', ''))}",
        ])

    def _render_round_review(self, review: dict[str, Any]) -> str:
        return "\n".join([
            "### 라운드 중재 기록",
            "",
            f"- 반복 주장: {self._list(review.get('repeated_claims', []))}",
            f"- 부족한 근거: {self._list(review.get('missing_evidence', []))}",
            f"- 진행 판단: {self._safe(review.get('reason', ''))}",
        ])

    def _render_evidence_cards(
        self,
        rounds: list[dict[str, Any]],
    ) -> str:
        evidence_items: list[dict[str, Any]] = []
        for round_data in rounds:
            for side in ("bull_response", "bear_response"):
                for issue in round_data.get(side, {}).get("issues", []):
                    for item in issue.get("evidence", []):
                        if isinstance(item, dict):
                            evidence_items.append(item)

        if not evidence_items:
            return "## 근거 원문\n\n연결된 원문 근거가 없습니다."

        sections = ["## 근거 원문"]
        for item in evidence_items:
            evidence_id = str(item.get("evidence_id", ""))
            verified = bool(item.get("verified"))
            status = "검증 완료" if verified else "원문 확인 불가"
            title = self._safe(item.get("title", "출처 확인 불가"))
            source_url = str(item.get("source_url", ""))
            context = str(item.get("context_text", ""))
            lines = [
                f'<a id="evidence-{evidence_id.lower()}"></a>',
                f"### [{self._safe(evidence_id)}] {title}",
                f"- 검증 상태: {status}",
                f"- 자료 유형: {self._safe(item.get('source_type', ''))}",
                f"- 게시일: {self._safe(item.get('published_at', '') or '확인 불가')}",
                f"- 문서 ID: {self._safe(item.get('document_id', '') or '없음')}",
                f"- 청크: {self._safe(item.get('chunk_id', '') or '없음')}",
            ]
            if source_url:
                lines.append(f"- [외부 원문 열기]({source_url})")
            else:
                lines.append("- 외부 원문 링크: 확인 불가")
            if verified:
                lines.extend([
                    "",
                    "**사용된 정확 인용**",
                    "",
                    self._blockquote(str(item.get("exact_quote", ""))),
                    "",
                    "**인용 문단 전체**",
                    "",
                    self._blockquote(context),
                ])
            else:
                lines.extend([
                    "",
                    "에이전트가 제출한 인용문을 실제 원문에서 찾지 못했습니다.",
                ])
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    def _render_debate_status(
        self,
        summary: dict[str, Any],
        stop_reason: str,
    ) -> str:
        return "\n".join([
            "## 토론 종료 상태",
            "",
            "| 구분 | 내용 |",
            "|---|---|",
            f"| 합의 사항 | {self._list(summary.get('agreements', []))} |",
            f"| 미해결 쟁점 | {self._list(summary.get('unresolved_issues', []))} |",
            f"| 추가 필요 근거 | {self._list(summary.get('required_evidence', []))} |",
            f"| 중재자 정리 | {self._cell(summary.get('summary', ''))} |",
            f"| 종료 사유 | {self._cell(stop_reason)} |",
        ])

    def _row(self, label: str, bull: Any, bear: Any) -> str:
        return f"| {label} | {self._cell(bull)} | {self._cell(bear)} |"

    def _cell(self, value: Any) -> str:
        return self._safe(value or "없음").replace("\n", "<br>")

    def _list(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "없음"
        return "<br>".join(f"• {self._cell(value)}" for value in values)

    def _evidence_links(self, values: Any) -> str:
        if not isinstance(values, list) or not values:
            return "없음"
        rendered = []
        for value in values:
            if not isinstance(value, dict):
                rendered.append(f"• {self._cell(value)}")
                continue
            evidence_id = str(value.get("evidence_id", ""))
            mark = "검증" if value.get("verified") else "미검증"
            reason = self._cell(value.get("reason", ""))
            rendered.append(
                f"• [{self._safe(evidence_id)}](#evidence-{evidence_id.lower()}) "
                f"({mark}) {reason}"
            )
        return "<br>".join(rendered)

    def _blockquote(self, value: str) -> str:
        return "\n".join(
            f"> {self._safe(line)}" for line in value.splitlines()
        )

    @staticmethod
    def _find_issue(turn: dict[str, Any], issue_id: str) -> dict[str, Any]:
        return next(
            (
                item for item in turn.get("issues", [])
                if str(item.get("issue_id", "")) == issue_id
            ),
            {},
        )

    @staticmethod
    def _safe(value: Any) -> str:
        return html.escape(str(value or ""), quote=False).replace("|", "\\|")

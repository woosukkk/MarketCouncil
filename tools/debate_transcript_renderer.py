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
        sections.append(
            self._render_issue_map(
                debate.get("navigation", {}) or {},
                agenda,
                debate.get("issue_statuses", []),
            )
        )

        navigation = debate.get("navigation", {}) or {}
        for index, issue in enumerate(agenda, 1):
            issue_id = str(issue.get("issue_id", ""))
            sections.append("\n".join([
                f'<a id="issue-{self._anchor(issue_id)}"></a>',
                f"## 논제 {index}. {self._safe(issue.get('title', ''))}",
                f"> {self._safe(issue.get('question', ''))}",
            ]))
            for round_data in rounds:
                round_number = self._round_number(round_data.get("round", ""))
                bull = round_data.get("bull_response", {}) or {}
                bear = round_data.get("bear_response", {}) or {}
                reviews = (
                    round_data.get("moderator_review", {}) or {}
                ).get("issue_reviews", [])
                sections.append(
                    self._render_issue_round(
                        issue,
                        bull,
                        bear,
                        reviews,
                        round_number,
                        navigation,
                    )
                )

        sections.append("## 라운드 진행 기록")
        for round_data in rounds:
            round_number = round_data.get("round", "")
            review = round_data.get("moderator_review", {}) or {}
            sections.append("\n".join([
                f"### {self._safe(round_number)}라운드",
                self._render_round_review(review),
            ]))

        sections.append(self._render_evidence_cards(rounds))
        sections.append(
            self._render_debate_status(
                debate.get("moderator_summary", {}) or {},
                str(debate.get("stop_reason", "")),
            )
        )
        sections.append(
            self._render_regime_analysis(
                debate.get("regime_analysis", {}) or {},
            )
        )
        return "\n\n".join(section for section in sections if section).strip() + "\n"

    def _render_issue_round(
        self,
        agenda: dict[str, Any],
        bull: dict[str, Any],
        bear: dict[str, Any],
        reviews: list[dict[str, Any]],
        round_number: int,
        navigation: dict[str, Any],
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
            f'<a id="issue-{self._anchor(issue_id)}-round-{round_number}"></a>',
            f"### {round_number}라운드",
            self._render_round_change(navigation, issue_id, round_number),
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
                "연결 논리",
                bull_issue.get("warrant"),
                bear_issue.get("warrant"),
            ),
            self._row(
                "조건·한계",
                bull_issue.get("qualifier"),
                bear_issue.get("qualifier"),
            ),
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

    def _render_issue_map(
        self,
        navigation: dict[str, Any],
        agenda: list[dict[str, Any]],
        statuses: list[dict[str, Any]],
    ) -> str:
        navigation_issues = {
            str(issue.get("issue_id", "")): issue
            for issue in navigation.get("issues", [])
        }
        status_by_id = {
            str(item.get("issue_id", "")): str(item.get("status", ""))
            for item in statuses
        }
        lines = ["## 쟁점 지도"]
        overview = str(navigation.get("overview", "")).strip()
        if overview:
            lines.extend(["", self._safe(overview)])
        lines.extend(["", "| 쟁점 | 상태 | 핵심 대립 |", "|---|---|---|"])
        for issue in agenda:
            issue_id = str(issue.get("issue_id", ""))
            guide = navigation_issues.get(issue_id, {})
            status_code = str(guide.get("status") or status_by_id.get(issue_id, ""))
            status = self.STATUS_LABELS.get(status_code, status_code or "미평가")
            title = self._safe(issue.get("title", ""))
            link = f"[{title}](#issue-{self._anchor(issue_id)})"
            disagreement = self._cell(guide.get("core_disagreement", "확인 불가"))
            lines.append(f"| {link} | {self._safe(status)} | {disagreement} |")
        return "\n".join(lines)

    def _render_round_change(
        self,
        navigation: dict[str, Any],
        issue_id: str,
        round_number: int,
    ) -> str:
        issue = next(
            (
                item for item in navigation.get("issues", [])
                if str(item.get("issue_id", "")) == issue_id
            ),
            {},
        )
        change = next(
            (
                item for item in issue.get("round_changes", [])
                if item.get("round") == round_number
            ),
            {},
        )
        if not change:
            return ""
        evidence = ", ".join(change.get("new_evidence_ids", [])) or "없음"
        concessions = "; ".join(change.get("concessions", [])) or "없음"
        return "\n".join([
            "",
            "**이 라운드의 변화**",
            f"- 상승 관점: {self._safe(change.get('bull_change', ''))}",
            f"- 하락 관점: {self._safe(change.get('bear_change', ''))}",
            f"- 새 근거: {self._safe(evidence)}",
            f"- 인정 사항: {self._safe(concessions)}",
            f"- 남은 질문: {self._safe(change.get('remaining_question', ''))}",
        ])

    def _render_round_review(self, review: dict[str, Any]) -> str:
        return "\n".join([
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
                f"- PDF 페이지: {self._safe(item.get('page_number', '') or '확인 불가')}",
            ]
            source_page_url = str(item.get("source_page_url") or source_url)
            if source_page_url:
                lines.append(f"- [외부 원문 열기]({source_page_url})")
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

    def _render_regime_analysis(self, analysis: dict[str, Any]) -> str:
        regimes = analysis.get("regimes", {})
        if not regimes:
            return ""
        bull = regimes.get("past_bull", {})
        bear = regimes.get("recent_bear", {})
        lines = ["## 3년 시계열 흐름"]
        display_series = analysis.get("display_series", {})
        series_sections = (
            ("최근 60거래일 · 일별", display_series.get("recent_daily", [])),
            ("최근 1년 · 월별", display_series.get("medium_monthly", [])),
            ("과거 · 분기별", display_series.get("historical_quarterly", [])),
        )
        for title, rows in series_sections:
            if rows:
                lines.extend(self._render_series_table(title, rows))
        lines.extend([
            "",
            "## 시장 국면 비교",
            "",
            self._safe(analysis.get("methodology", {}).get("description", "")),
            "",
            "| 구분 | 과거 상승장 | 최근 하락장 |",
            "|---|---|---|",
            (
                f"| 기간 | {self._cell(self._period(bull))} | "
                f"{self._cell(self._period(bear))} |"
            ),
        ])
        for row in analysis.get("comparison", []):
            unit = str(row.get("unit", ""))
            lines.append(
                f"| {self._cell(row.get('metric'))} | "
                f"{self._cell(self._metric(row.get('past_bull'), unit))} | "
                f"{self._cell(self._metric(row.get('recent_bear'), unit))} |"
            )

        reasons = analysis.get("reasons", {})
        bull_reasons = reasons.get("past_bull", [])
        bear_reasons = reasons.get("recent_bear", [])
        lines.extend([
            "",
            "### 상승·하락 이유 비교",
            "",
            "| 순위 | 과거 상승장의 이유 | 근거 | 최근 하락장의 이유 | 근거 |",
            "|---:|---|---|---|---|",
        ])
        for index in range(max(len(bull_reasons), len(bear_reasons), 2)):
            bull_reason = bull_reasons[index] if index < len(bull_reasons) else {}
            bear_reason = bear_reasons[index] if index < len(bear_reasons) else {}
            lines.append(
                f"| {index + 1} | {self._cell(bull_reason.get('claim', '추가 데이터 필요'))} | "
                f"{self._regime_evidence_links(bull_reason)} | "
                f"{self._cell(bear_reason.get('claim', '추가 데이터 필요'))} | "
                f"{self._regime_evidence_links(bear_reason)} |"
            )

        evidence_items: dict[str, dict[str, Any]] = {}
        for regime_reasons in reasons.values():
            for reason in regime_reasons:
                for item in reason.get("evidence", []):
                    evidence_id = str(item.get("evidence_id", ""))
                    if evidence_id:
                        evidence_items.setdefault(evidence_id, item)
        if evidence_items:
            lines.extend(["", "### 국면 근거 원문"])
        for evidence_id, item in evidence_items.items():
            source_url = str(item.get("source_page_url") or item.get("source_url", ""))
            lines.extend([
                "",
                f'<a id="regime-evidence-{evidence_id.lower()}"></a>',
                f"#### [{self._safe(evidence_id)}] {self._safe(item.get('title', '출처 확인 불가'))}",
                f"- 게시일: {self._safe(item.get('published_at', '') or '확인 불가')}",
                f"- PDF 페이지: {self._safe(item.get('page_number', '') or '확인 불가')}",
                f"- 1일 가격 반응: {self._safe(self._metric(item.get('price_reaction_1d_pct'), '%'))}",
                f"- 5일 가격 반응: {self._safe(self._metric(item.get('price_reaction_5d_pct'), '%'))}",
                f"- 시장조정 5일 반응: {self._safe(self._metric(item.get('market_adjusted_5d_pct'), '%'))}",
            ])
            if source_url:
                lines.append(f"- [외부 원문 열기]({source_url})")
            lines.extend([
                "",
                "**정확 인용**",
                "",
                self._blockquote(str(item.get("exact_quote", "확인 불가"))),
                "",
                "**인용 문단 전체**",
                "",
                self._blockquote(str(item.get("context_text", "확인 불가"))),
            ])

        limitations = analysis.get("limitations", [])
        if limitations:
            lines.extend(["", "### 분석 한계", "", *[f"- {self._safe(item)}" for item in limitations]])
        return "\n".join(lines)

    def _render_series_table(
        self,
        title: str,
        rows: list[dict[str, Any]],
    ) -> list[str]:
        lines = [
            "",
            f"### {title}",
            "",
            "| 기간 | 시가 | 고가 | 저가 | 종가 | 수익률 | 최대 낙폭 | 변동성 | 평균 거래량 | 시장 대비 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for row in rows:
            lines.append(
                f"| {self._cell(row.get('period'))} | "
                f"{self._cell(row.get('open'))} | {self._cell(row.get('high'))} | "
                f"{self._cell(row.get('low'))} | {self._cell(row.get('close'))} | "
                f"{self._cell(self._metric(row.get('return_pct'), '%'))} | "
                f"{self._cell(self._metric(row.get('max_drawdown_pct'), '%'))} | "
                f"{self._cell(self._metric(row.get('annualized_volatility_pct'), '%'))} | "
                f"{self._cell(row.get('average_volume'))} | "
                f"{self._cell(self._metric(row.get('excess_return_pct'), '%'))} |"
            )
        return lines

    def _regime_evidence_links(self, reason: dict[str, Any]) -> str:
        links = [
            f"[{self._safe(item.get('evidence_id'))}]"
            f"(#regime-evidence-{str(item.get('evidence_id', '')).lower()})"
            for item in reason.get("evidence", [])
            if item.get("evidence_id")
        ]
        return "<br>".join(links) or "확인 불가"

    @staticmethod
    def _period(regime: dict[str, Any]) -> str:
        start = str(regime.get("start_date", ""))
        end = str(regime.get("end_date", ""))
        return f"{start} ~ {end}" if start and end else "확인 불가"

    @staticmethod
    def _metric(value: Any, unit: str) -> str:
        if value is None:
            return "확인 불가"
        return f"{value}{unit}"

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
    def _anchor(value: str) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value).strip("-").lower()

    @staticmethod
    def _round_number(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

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

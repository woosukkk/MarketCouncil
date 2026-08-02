import html
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.debate_report_renderer import filter_visible_judge_result


def humanize_judge_result(result: Any) -> str:
    text = filter_visible_judge_result(result)
    rating_labels = {
        "Strong Bull": "강한 상승",
        "Bull": "상승",
        "Neutral": "중립",
        "Bear": "하락",
        "Strong Bear": "강한 하락",
    }
    confidence_labels = {"High": "높음", "Medium": "보통", "Low": "낮음"}
    rating_match = re.search(r"(?im)(Final Rating\s*:\s*)(.+)$", text)
    if rating_match:
        value = rating_match.group(2).strip()
        text = text[:rating_match.start()] + (
            f"최종 등급: {rating_labels.get(value, value)}"
        ) + text[rating_match.end():]
    confidence_match = re.search(r"(?im)(Confidence\s*:\s*)(.+)$", text)
    if confidence_match:
        value = confidence_match.group(2).strip()
        text = text[:confidence_match.start()] + (
            f"신뢰도: {confidence_labels.get(value, value)}"
        ) + text[confidence_match.end():]
    text = re.sub(r"(?im)Bull Score\s*:", "상승 점수:", text)
    text = re.sub(r"(?im)Bear Score\s*:", "하락 점수:", text)
    text = re.sub(r"\bBull\b", "상승 관점", text)
    text = re.sub(r"\bBear\b", "하락 관점", text)
    return text


class MarkdownReportRenderer:
    STATUS_LABELS = {
        "OPEN": "답변 대기",
        "CONTESTED": "의견 대립",
        "RESOLVED": "쟁점 해소",
        "STALEMATE": "반복·교착",
        "UNKNOWN": "자료 부족",
    }
    RATING_LABELS = {
        "Strong Bull": "강한 상승",
        "Bull": "상승",
        "Neutral": "중립",
        "Bear": "하락",
        "Strong Bear": "강한 하락",
    }
    CONFIDENCE_LABELS = {
        "High": "높음",
        "Medium": "보통",
        "Low": "낮음",
    }

    def __init__(
        self,
        output_dir: Path = Path("results/comparison"),
        line_width: int = 80,
    ) -> None:
        self.output_dir = output_dir
        self.line_width = line_width

    def save(self, analysis_data: dict[str, Any]) -> str:
        company_name = str(analysis_data.get("company_name", "company"))
        return self.save_content(company_name, self.render(analysis_data))

    def save_content(self, company_name: str, markdown: str) -> str:
        safe_company = re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            company_name,
        ).strip("_") or "company"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.output_dir / f"{safe_company}_{timestamp}.md"
        file_path.write_text(markdown.strip() + "\n", encoding="utf-8")
        return str(file_path)

    def normalize_generated(self, markdown: str) -> str:
        output: list[str] = []
        for raw_line in markdown.splitlines():
            line = raw_line.rstrip()
            if not line or line.startswith(("#", "|", "```")):
                output.append(line)
                continue
            prefix = ""
            content = line
            match = re.match(r"^(>\s+|\s*[-*+]\s+|\s*\d+\.\s+)(.*)$", line)
            if match:
                prefix, content = match.groups()
            width = max(self.line_width - self._width(prefix), 20)
            wrapped = self._wrap_display(content, width)
            for index, part in enumerate(wrapped):
                visible_prefix = prefix if index == 0 else " " * self._width(prefix)
                suffix = "  " if index < len(wrapped) - 1 else ""
                output.append(f"{visible_prefix}{part}{suffix}")
        return "\n".join(output).strip() + "\n"

    def render(self, analysis_data: dict[str, Any]) -> str:
        company_name = self._safe(analysis_data.get("company_name", ""))
        raw_judge_result = filter_visible_judge_result(
            analysis_data.get("judge_result", "")
        )
        overall = analysis_data.get("axis_judgment", {}).get("overall", {})
        rating, bull_score, bear_score, confidence = (
            (
                str(overall.get("rating", "확인 불가")),
                int(overall.get("bull_score", 50)),
                int(overall.get("bear_score", 50)),
                str(overall.get("confidence", "확인 불가")),
            )
            if overall
            else self._judge_metrics(raw_judge_result)
        )
        judge_result = humanize_judge_result(raw_judge_result)
        debate_applied = "적용" if analysis_data.get("debate_applied") else "미적용"
        sections = [
            f"# {company_name} 투자 분석",
            f"> 분석 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "## 최종 판단 한눈에 보기",
            "| 항목 | 결과 |",
            "|---|---|",
            f"| 최종 등급 | {self._safe(self.RATING_LABELS.get(rating, rating))} |",
            f"| 상승 점수 | {bull_score} |",
            f"| 하락 점수 | {bear_score} |",
            f"| 신뢰도 | {self._safe(self.CONFIDENCE_LABELS.get(confidence, confidence))} |",
            f"| 토론 적용 | {debate_applied} |",
            self._render_axis_judgments(analysis_data),
            self._render_axis_changes(analysis_data.get("axis_changes", [])),
            "## Judge 종합 판단",
            self._wrap_markdown(judge_result),
            self._render_sentiment(analysis_data.get("sentiment_result", {}) or {}),
            self._render_debate(analysis_data.get("analysis_debate", {}) or {}),
            "## 최종 결론",
            self._wrap_paragraph(self._extract_final_conclusion(judge_result)),
        ]
        return "\n\n".join(section for section in sections if section).strip() + "\n"

    def _render_axis_judgments(self, analysis_data: dict[str, Any]) -> str:
        axes = {
            axis.get("id"): axis
            for axis in analysis_data.get("analysis_axes", [])
            if isinstance(axis, dict)
        }
        judgments = analysis_data.get("axis_judgment", {}).get(
            "axis_judgments", []
        )
        if not judgments:
            return ""
        labels = {-2: "매우 부정", -1: "부정", 0: "중립", 1: "긍정", 2: "매우 긍정"}
        lines = [
            "## 분석 축별 판단",
            "| 분석 축 | 판정 | 신뢰도 | 판단 근거 |",
            "|---|---:|---|---|",
        ]
        for item in judgments:
            axis = axes.get(item.get("axis_id"), {})
            label = self._safe(axis.get("label", item.get("axis_id", "")))
            if item.get("status") == "unavailable":
                verdict = "확인 불가"
            else:
                value = int(item.get("verdict", 0))
                verdict = f"{labels.get(value, '중립')} ({value:+d})"
            lines.append(
                f"| {label} | {self._safe(verdict)} | "
                f"{self._safe(item.get('confidence', 'low'))} | "
                f"{self._wrap_cell(item.get('reason', ''), 48)} |"
            )
        coverage = analysis_data.get("axis_judgment", {}).get(
            "overall", {}
        ).get("evidence_coverage")
        if coverage is not None:
            lines.extend(["", f"> 근거 충족률: {float(coverage):.1%}"])
        return "\n".join(lines)

    def _render_axis_changes(self, changes: list[dict[str, Any]]) -> str:
        if not changes:
            return ""
        lines = [
            "## 이전 분석 대비 변화",
            "| 분석 축 | 이전 | 현재 |",
            "|---|---:|---:|",
        ]
        for change in changes:
            previous = (
                "확인 불가" if change.get("previous_status") == "unavailable"
                else f"{int(change.get('previous_verdict', 0)):+d}"
            )
            current = (
                "확인 불가" if change.get("current_status") == "unavailable"
                else f"{int(change.get('current_verdict', 0)):+d}"
            )
            lines.append(
                f"| {self._safe(change.get('label', ''))} | {previous} | {current} |"
            )
        return "\n".join(lines)

    def _render_sentiment(self, sentiment: dict[str, Any]) -> str:
        total = self._number(sentiment.get("total_count", 0))
        positive = self._number(sentiment.get("positive_count", 0))
        neutral = self._number(sentiment.get("neutral_count", 0))
        negative = self._number(sentiment.get("negative_count", 0))
        positive_ratio = self._number(sentiment.get("positive_ratio", 0))
        neutral_ratio = self._number(sentiment.get("neutral_ratio", 0))
        negative_ratio = self._number(sentiment.get("negative_ratio", 0))
        overview = (
            f"전체 {total}건의 주요 사건 중 긍정 {positive}건({positive_ratio}%), "
            f"중립 {neutral}건({neutral_ratio}%), 부정 {negative}건({negative_ratio}%)으로 "
            "분류됐다."
        )
        lines = [
            "## 뉴스 민심",
            self._wrap_paragraph(overview),
        ]
        summary = str(sentiment.get("summary", "")).strip()
        if summary:
            lines.extend(["### 핵심 요약", self._wrap_paragraph(summary)])

        articles = sentiment.get("articles", [])
        for value, title in (("positive", "주요 긍정 사건"), ("negative", "주요 부정 사건")):
            selected = [
                article for article in articles
                if isinstance(article, dict) and article.get("sentiment") == value
            ][:2]
            if selected:
                lines.append(f"### {title}")
                lines.extend(self._article_line(article) for article in selected)
        return "\n\n".join(lines)

    def _render_debate(self, debate: dict[str, Any]) -> str:
        if not debate:
            return "## 토론 시각화\n\n적용된 토론 결과가 없습니다."
        agenda = debate.get("agenda", [])
        rounds = debate.get("rounds", [])
        latest = rounds[-1] if rounds else {}
        bull = latest.get("bull_response", {}) or {}
        bear = latest.get("bear_response", {}) or {}
        reviews = latest.get("moderator_review", {}).get("issue_reviews", [])
        sections = ["## 토론 시각화"]
        for index, issue in enumerate(agenda, 1):
            sections.append(
                self._render_issue_table(index, issue, bull, bear, reviews)
            )
        summary = debate.get("moderator_summary", {}) or {}
        sections.append(self._render_debate_result(summary))
        return "\n\n".join(sections)

    def _render_issue_table(
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
            (item for item in reviews if str(item.get("issue_id", "")) == issue_id),
            {},
        )
        bull_claim = bull_issue.get("claim") or agenda.get("bull_claim", "")
        bear_claim = bear_issue.get("claim") or agenda.get("bear_claim", "")
        status = self.STATUS_LABELS.get(
            str(review.get("status", "")),
            str(review.get("status", "미평가")),
        )
        return "\n".join([
            f"### 논제 {index}. {self._safe(agenda.get('title', ''))}",
            f"> {self._wrap_cell(agenda.get('question', ''), 64)}",
            "",
            "| 상승 관점 | ↔ | 하락 관점 |",
            "|---|:---:|---|",
            f"| **주장**<br>{self._wrap_cell(bull_claim)} | 주장 | **주장**<br>{self._wrap_cell(bear_claim)} |",
            f"| **반론**<br>{self._wrap_cell(bull_issue.get('response', ''))} | 반박 | **반론**<br>{self._wrap_cell(bear_issue.get('response', ''))} |",
            f"| **근거**<br>{self._list_cell(bull_issue.get('evidence', []))} | 근거 | **근거**<br>{self._list_cell(bear_issue.get('evidence', []))} |",
            f"| **사례·수치**<br>{self._wrap_cell(bull_issue.get('example_or_data', '확인된 사례·수치 없음'))} | 사례 | **사례·수치**<br>{self._wrap_cell(bear_issue.get('example_or_data', '확인된 사례·수치 없음'))} |",
            f"| **인정 사항**<br>{self._wrap_cell(bull_issue.get('concession', ''))} |  | **인정 사항**<br>{self._wrap_cell(bear_issue.get('concession', ''))} |",
            "",
            f"**중재 결과:** {self._safe(status)}",
            self._wrap_paragraph(str(review.get("assessment", ""))),
        ])

    def _render_debate_result(self, summary: dict[str, Any]) -> str:
        return "\n".join([
            "### 토론 결과",
            "",
            "| 구분 | 내용 |",
            "|---|---|",
            f"| 합의 사항 | {self._list_cell(summary.get('agreements', []), 58)} |",
            f"| 미해결 쟁점 | {self._list_cell(summary.get('unresolved_issues', []), 58)} |",
            f"| 최종 결론 | {self._wrap_cell(summary.get('summary', ''), 58)} |",
        ])

    def _article_line(self, article: dict[str, Any]) -> str:
        title = self._safe(article.get("title", "제목 없음"))
        source = self._safe(article.get("source", "출처 불명"))
        date = self._safe(article.get("published_date", "날짜 불명"))
        return self._wrap_markdown(f"- {title} — {source}, {date}")

    @staticmethod
    def _find_issue(turn: dict[str, Any], issue_id: str) -> dict[str, Any]:
        return next(
            (item for item in turn.get("issues", []) if str(item.get("issue_id", "")) == issue_id),
            {},
        )

    def _wrap_markdown(self, text: Any) -> str:
        output: list[str] = []
        for raw_line in str(text or "").splitlines():
            line = raw_line.rstrip()
            if not line or line.startswith(("#", "|", "```")):
                output.append(self._safe(line))
                continue
            prefix = ""
            content = line
            match = re.match(r"^(\s*[-*+]\s+)(.*)$", line)
            if match:
                prefix, content = match.groups()
            wrapped = self._wrap_display(content, self.line_width - self._width(prefix))
            for index, part in enumerate(wrapped):
                visible_prefix = prefix if index == 0 else " " * self._width(prefix)
                output.append(f"{visible_prefix}{self._safe(part)}")
        return "  \n".join(output)

    def _wrap_paragraph(self, text: Any) -> str:
        return "  \n".join(
            self._safe(part) for part in self._wrap_display(str(text or ""), self.line_width)
        )

    def _wrap_cell(self, value: Any, width: int = 32) -> str:
        text = str(value or "없음").replace("|", "\\|")
        return "<br>".join(self._safe(part) for part in self._wrap_display(text, width))

    def _list_cell(self, items: list[Any], width: int = 32) -> str:
        if not items:
            return "없음"
        return "<br>".join(
            f"• {self._wrap_cell(item, width)}" for item in items
        )

    @classmethod
    def _wrap_display(cls, text: str, width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            chunks = cls._split_long_word(word, width)
            for chunk in chunks:
                candidate = f"{current} {chunk}".strip()
                if current and cls._width(candidate) > width:
                    lines.append(current)
                    current = chunk
                else:
                    current = candidate
        if current:
            lines.append(current)
        return lines

    @classmethod
    def _split_long_word(cls, word: str, width: int) -> list[str]:
        if cls._width(word) <= width:
            return [word]
        chunks: list[str] = []
        current = ""
        for character in word:
            if current and cls._width(current + character) > width:
                chunks.append(current)
                current = character
            else:
                current += character
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _width(text: str) -> int:
        return sum(
            2 if unicodedata.east_asian_width(character) in {"W", "F"} else 1
            for character in text
        )

    @staticmethod
    def _judge_metrics(result: str) -> tuple[str, int, int, str]:
        def value(label: str, default: str) -> str:
            match = re.search(rf"(?im)^-?\s*{re.escape(label)}\s*:\s*(.+)$", result)
            return match.group(1).strip() if match else default

        def score(label: str, default: int) -> int:
            match = re.search(rf"(?im)^-?\s*{re.escape(label)}\s*:\s*(\d+)", result)
            return min(max(int(match.group(1)), 0), 100) if match else default

        bull_score = score("Bull Score", 50)
        bear_score = score("Bear Score", 100 - bull_score)
        return value("Final Rating", "확인 불가"), bull_score, bear_score, value("Confidence", "확인 불가")

    @staticmethod
    def _extract_final_conclusion(result: str) -> str:
        match = re.search(
            r"(?ms)^#\s*최종 판단\s*(.*?)(?=^#\s|\Z)",
            result,
        )
        if match and match.group(1).strip():
            return match.group(1).strip()
        lines = [
            line.strip("- ")
            for line in result.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        return " ".join(lines[-3:]) if lines else "최종 결론을 확인할 수 없습니다."

    @staticmethod
    def _number(value: Any) -> str:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return "0"
        return str(int(number)) if number.is_integer() else f"{number:.1f}"

    @staticmethod
    def _safe(value: Any) -> str:
        return html.escape(str(value or ""), quote=False)

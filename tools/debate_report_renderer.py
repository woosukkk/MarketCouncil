import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def filter_visible_judge_result(result: Any) -> str:
    text = str(result or "")
    return re.sub(
        r"(?ms)^#\s*추가 확인 데이터\s*.*?(?=^#\s|\Z)",
        "",
        text,
    ).strip()


class DebateReportRenderer:
    def __init__(
        self,
        output_dir: Path = Path("results/comparison"),
    ) -> None:
        self.output_dir = output_dir

    def save(self, analysis_data: dict[str, Any]) -> str:
        company_name = str(analysis_data.get("company_name", "company"))
        safe_company = re.sub(
            r"[^0-9A-Za-z가-힣._-]+",
            "_",
            company_name,
        ).strip("_") or "company"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.output_dir / f"{safe_company}_{timestamp}.html"
        file_path.write_text(self.render(analysis_data), encoding="utf-8")
        return str(file_path)

    def render(self, analysis_data: dict[str, Any]) -> str:
        company_name = self._escape(analysis_data.get("company_name", ""))
        debate = analysis_data.get("analysis_debate", {}) or {}
        judge_result = filter_visible_judge_result(
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
            else self._judge_metrics(judge_result)
        )
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{company_name} MarketCouncil 분석</title>
<style>
:root {{ --bg:#f4f6f8; --panel:#fff; --text:#17202a; --muted:#667085;
 --bull:#137a4b; --bull-bg:#ecfdf3; --bear:#b42318; --bear-bg:#fff1f0;
 --mod:#3448a5; --mod-bg:#eef1ff; --line:#d9dee7; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text);
 font-family:"Pretendard","Noto Sans KR",Arial,sans-serif; line-height:1.65; }}
main {{ width:min(1180px,94vw); margin:32px auto 72px; }}
header,.section,.issue,.summary-card {{ background:var(--panel); border:1px solid var(--line);
 border-radius:16px; box-shadow:0 8px 24px rgba(16,24,40,.06); }}
header,.section {{ padding:24px; margin:20px 0; }}
h1,h2,h3,h4,p {{ margin-top:0; }} h1 {{ margin-bottom:6px; }}
.muted {{ color:var(--muted); }}
.decision-grid {{ display:grid; grid-template-columns:2fr 1fr; gap:14px; }}
.metric {{ padding:16px; border:1px solid var(--line); border-radius:12px; background:#fafbfc; }}
.metric strong {{ display:block; font-size:1.35rem; }}
.score-labels {{ display:flex; justify-content:space-between; margin-top:12px; font-weight:800; }}
.score-bar {{ display:flex; height:18px; overflow:hidden; border-radius:999px; background:#e5e7eb; }}
.score-bull {{ background:var(--bull); }} .score-bear {{ background:var(--bear); }}
.sentiment-grid,.summary-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
.sentiment-card,.summary-card {{ padding:17px; text-align:center; box-shadow:none; }}
.sentiment-card strong {{ display:block; font-size:1.5rem; }}
.agenda {{ border-left:5px solid var(--mod); padding:16px; background:var(--mod-bg);
 border-radius:10px; margin-bottom:14px; }}
.question {{ color:var(--mod); font-weight:800; }}
.two-column {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.side {{ padding:20px; border-radius:12px; min-width:0; }}
.bull {{ background:var(--bull-bg); border:1px solid #a6e6c4; }}
.bear {{ background:var(--bear-bg); border:1px solid #f3b4ae; }}
.bull h4 {{ color:var(--bull); }} .bear h4 {{ color:var(--bear); }}
.label {{ display:block; margin-top:12px; color:var(--muted); font-size:.82rem; font-weight:800; }}
.side p {{ margin:3px 0 0; white-space:pre-wrap; overflow-wrap:anywhere; }}
.issue {{ padding:18px; margin:16px 0; box-shadow:none; }}
.moderator {{ margin-top:15px; padding:15px; border-left:5px solid var(--mod);
 background:var(--mod-bg); border-radius:10px; }}
.badge {{ display:inline-block; margin-left:8px; padding:2px 9px; border-radius:999px;
 color:#fff; background:var(--mod); font-size:.78rem; }}
ul {{ margin:5px 0 0; padding-left:20px; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#111827; color:#e5e7eb;
 border-radius:12px; padding:18px; overflow:auto; }}
@media (max-width:760px) {{ .decision-grid,.two-column,.sentiment-grid,.summary-grid {{ grid-template-columns:1fr; }} }}
</style></head><body><main>
<header><h1>{company_name}</h1><p class="muted">MarketCouncil 종합 분석 · {generated_at}</p></header>
<section class="section"><h2>최종 판단 한눈에 보기</h2>
<div class="decision-grid"><div class="metric"><span class="muted">Final Rating</span>
<strong>{self._escape(rating)}</strong><div class="score-labels"><span>Bull {bull_score}</span><span>Bear {bear_score}</span></div>
<div class="score-bar"><div class="score-bull" style="width:{bull_score}%"></div>
<div class="score-bear" style="width:{bear_score}%"></div></div></div>
<div class="metric"><span class="muted">Confidence</span><strong>{self._escape(confidence)}</strong></div></div></section>
{self._render_axes(analysis_data)}
{self._render_axis_changes(analysis_data.get("axis_changes", []))}
<section class="section"><h2>Judge 종합 판단</h2><pre>{self._escape(judge_result)}</pre></section>
{self._render_sentiment(analysis_data.get("sentiment_result", {}))}
{self._render_debate(debate)}
<p class="muted">토론 적용 여부: {self._escape(analysis_data.get("debate_applied", False))}
 · 토론 출처: {self._escape(analysis_data.get("debate_source", "none"))}</p>
</main></body></html>"""

    def _render_axes(self, analysis_data: dict[str, Any]) -> str:
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
        rows = []
        for item in judgments:
            axis = axes.get(item.get("axis_id"), {})
            verdict = (
                "확인 불가"
                if item.get("status") == "unavailable"
                else labels.get(int(item.get("verdict", 0)), "중립")
            )
            rows.append(
                "<tr>"
                f"<td>{self._escape(axis.get('label', item.get('axis_id', '')))}</td>"
                f"<td>{self._escape(verdict)}</td>"
                f"<td>{self._escape(item.get('confidence', 'low'))}</td>"
                f"<td>{self._escape(item.get('reason', ''))}</td>"
                "</tr>"
            )
        coverage = analysis_data.get("axis_judgment", {}).get(
            "overall", {}
        ).get("evidence_coverage", 0)
        return (
            '<section class="section"><h2>분석 축별 판단</h2>'
            '<table style="width:100%;border-collapse:collapse">'
            '<thead><tr><th>분석 축</th><th>판정</th><th>신뢰도</th><th>판단 근거</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>"
            f'<p class="muted">근거 충족률: {float(coverage):.1%}</p></section>'
        )

    def _render_axis_changes(self, changes: list[dict[str, Any]]) -> str:
        if not changes:
            return ""
        rows = []
        for change in changes:
            previous = (
                "확인 불가" if change.get("previous_status") == "unavailable"
                else f"{int(change.get('previous_verdict', 0)):+d}"
            )
            current = (
                "확인 불가" if change.get("current_status") == "unavailable"
                else f"{int(change.get('current_verdict', 0)):+d}"
            )
            rows.append(
                "<tr>"
                f"<td>{self._escape(change.get('label', ''))}</td>"
                f"<td>{self._escape(previous)}</td>"
                f"<td>{self._escape(current)}</td>"
                "</tr>"
            )
        return (
            '<section class="section"><h2>이전 분석 대비 변화</h2>'
            '<table style="width:100%;border-collapse:collapse">'
            '<thead><tr><th>분석 축</th><th>이전</th><th>현재</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></section>"
        )

    def _render_sentiment(self, sentiment: dict[str, Any]) -> str:
        return f"""<section class="section"><h2>뉴스 민심</h2>
<div class="sentiment-grid">
{self._sentiment_card("긍정", sentiment.get("positive_ratio", 0), sentiment.get("positive_count", 0))}
{self._sentiment_card("중립", sentiment.get("neutral_ratio", 0), sentiment.get("neutral_count", 0))}
{self._sentiment_card("부정", sentiment.get("negative_ratio", 0), sentiment.get("negative_count", 0))}
</div><p>{self._escape(sentiment.get("summary", ""))}</p>
{self._render_emotion_summary(sentiment.get("emotion_summary", {}))}</section>"""

    def _render_emotion_summary(self, summary: dict[str, Any]) -> str:
        axes = summary.get("axes", []) if isinstance(summary, dict) else []
        if not axes:
            return ""
        direction_labels = {
            "expectation": ("비관", "낙관"),
            "risk_emotion": ("공포", "안도"),
            "certainty": ("불확실", "확신"),
            "expectation_gap": ("실망", "긍정적 놀라움"),
        }
        rows = []
        for axis in axes:
            axis_id = str(axis.get("axis_id", ""))
            if axis.get("status") == "unavailable":
                direction = "확인 불가"
                score = "-"
            else:
                value = float(axis.get("score", 0))
                negative, positive = direction_labels.get(axis_id, ("부정", "긍정"))
                direction = positive if value > 0.25 else negative if value < -0.25 else "중립"
                score = f"{value:+.2f}"
            rows.append(
                "<tr>"
                f"<td>{self._escape(axis.get('label', axis_id))}</td>"
                f"<td>{self._escape(direction)}</td>"
                f"<td>{self._escape(score)}</td>"
                f"<td>{self._escape(axis.get('confidence', 'low'))}</td>"
                f"<td>{self._escape(axis.get('evidence_count', 0))}</td>"
                "</tr>"
            )
        actors = summary.get("actor_distribution", {})
        actor_labels = {
            "investor": "투자자",
            "consumer": "소비자",
            "management": "경영진",
            "analyst": "애널리스트",
            "policy": "정책기관",
            "mixed": "복수 주체",
            "unknown": "주체 불명",
        }
        actor_text = ", ".join(
            f"{actor_labels.get(str(actor), str(actor))} {int(count)}건"
            for actor, count in actors.items()
        ) if isinstance(actors, dict) else ""
        return (
            '<h3>다차원 감정 축</h3>'
            '<table style="width:100%;border-collapse:collapse">'
            '<thead><tr><th>감정 축</th><th>방향</th><th>점수</th><th>신뢰도</th><th>근거 사건</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table>"
            '<p class="muted">감정 축은 보조 신호이며 투자 결론이 아닙니다.</p>'
            f'<p class="muted">감정 주체 분포: {self._escape(actor_text or "확인 불가")}</p>'
        )

    def _render_debate(self, debate: dict[str, Any]) -> str:
        if not debate:
            return '<section class="section"><h2>토론 시각화</h2><p>적용된 토론 결과가 없습니다.</p></section>'
        agenda = debate.get("agenda", [])
        rounds = debate.get("rounds", [])
        latest = rounds[-1] if rounds else {}
        bull = latest.get("bull_response", {}) or {}
        bear = latest.get("bear_response", {}) or {}
        reviews = latest.get("moderator_review", {}).get("issue_reviews", [])
        issues_html = "".join(
            self._render_final_issue(index, issue, bull, bear, reviews)
            for index, issue in enumerate(agenda, 1)
        )
        summary = debate.get("moderator_summary", {}) or {}
        return f"""<section class="section"><h2>토론 핵심 시각화</h2>
<p class="muted">최신 라운드 기준 핵심 주장과 반론입니다.</p>{issues_html}
<h3>토론 결과</h3><div class="summary-grid">
{self._summary_card("합의 사항", summary.get("agreements", []))}
{self._summary_card("미해결 쟁점", summary.get("unresolved_issues", []))}
</div><div class="moderator"><strong>중재자 최종 요약</strong>
<p>{self._escape(summary.get("summary", ""))}</p></div></section>"""

    def _render_final_issue(
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
        return f"""<article class="issue"><div class="agenda">
<h3>논제 {index}. {self._escape(agenda.get("title", ""))}</h3>
<p class="question">{self._escape(agenda.get("question", ""))}</p></div>
<div class="two-column">
{self._turn_card("Bull", agenda.get("bull_claim", ""), bull_issue, "bull")}
{self._turn_card("Bear", agenda.get("bear_claim", ""), bear_issue, "bear")}
</div><div class="moderator"><strong>중재자 평가</strong>
<span class="badge">{self._escape(review.get("status", "미평가"))}</span>
<p>{self._escape(review.get("assessment", ""))}</p></div></article>"""

    def _turn_card(
        self,
        role: str,
        initial_claim: Any,
        issue: dict[str, Any],
        css_class: str,
    ) -> str:
        return f"""<div class="side {css_class}"><h4>{role}</h4>
<span class="label">핵심 주장</span><p>{self._escape(initial_claim)}</p>
<span class="label">상대 주장</span><p>{self._escape(issue.get("target_claim", ""))}</p>
<span class="label">반론</span><p>{self._escape(issue.get("response", ""))}</p>
<span class="label">반론 근거</span>{self._list(issue.get("evidence", []))}
<span class="label">인정하는 부분</span><p>{self._escape(issue.get("concession", ""))}</p></div>"""

    @staticmethod
    def _find_issue(turn: dict[str, Any], issue_id: str) -> dict[str, Any]:
        return next(
            (item for item in turn.get("issues", []) if str(item.get("issue_id", "")) == issue_id),
            {},
        )

    @staticmethod
    def _judge_metrics(result: str) -> tuple[str, int, int, str]:
        def text_value(label: str, default: str) -> str:
            match = re.search(rf"(?im)^-?\s*{re.escape(label)}\s*:\s*(.+)$", result)
            return match.group(1).strip() if match else default

        def score(label: str, default: int) -> int:
            match = re.search(rf"(?im)^-?\s*{re.escape(label)}\s*:\s*(\d+)", result)
            return min(max(int(match.group(1)), 0), 100) if match else default

        bull_score = score("Bull Score", 50)
        bear_score = score("Bear Score", 100 - bull_score)
        total = bull_score + bear_score
        if total != 100 and total > 0:
            bull_score = round(bull_score / total * 100)
            bear_score = 100 - bull_score
        return (
            text_value("Final Rating", "확인 불가"),
            bull_score,
            bear_score,
            text_value("Confidence", "확인 불가"),
        )

    def _sentiment_card(self, title: str, ratio: Any, count: Any) -> str:
        return f"""<div class="sentiment-card"><span class="muted">{self._escape(title)}</span>
<strong>{self._escape(ratio)}%</strong><span>{self._escape(count)}건</span></div>"""

    def _summary_card(self, title: str, items: list[Any]) -> str:
        return f'<div class="summary-card"><h4>{self._escape(title)}</h4>{self._list(items)}</div>'

    def _list(self, items: list[Any]) -> str:
        if not items:
            return "<p>없음</p>"
        return "<ul>" + "".join(f"<li>{self._escape(item)}</li>" for item in items) + "</ul>"

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value or ""))

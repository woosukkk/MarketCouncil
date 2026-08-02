import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


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
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
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
header {{ padding:28px; margin-bottom:22px; }}
h1,h2,h3,h4,p {{ margin-top:0; }}
h1 {{ margin-bottom:6px; }} h2 {{ margin-bottom:18px; }}
.muted {{ color:var(--muted); }}
.section {{ padding:24px; margin:20px 0; }}
.agenda {{ border-left:5px solid var(--mod); padding:18px; margin:14px 0;
  background:var(--mod-bg); border-radius:10px; }}
.question {{ font-weight:700; color:var(--mod); }}
.two-column {{ display:grid; grid-template-columns:1fr 1fr; gap:18px; }}
.side {{ padding:20px; border-radius:12px; min-width:0; }}
.bull {{ background:var(--bull-bg); border:1px solid #a6e6c4; }}
.bear {{ background:var(--bear-bg); border:1px solid #f3b4ae; }}
.bull h4 {{ color:var(--bull); }} .bear h4 {{ color:var(--bear); }}
.label {{ display:block; margin-top:12px; font-size:.82rem; font-weight:800;
  text-transform:uppercase; color:var(--muted); }}
.side p {{ margin:3px 0 0; white-space:pre-wrap; overflow-wrap:anywhere; }}
ul {{ margin:5px 0 0; padding-left:20px; }}
.issue {{ padding:18px; margin:16px 0; box-shadow:none; }}
details.round {{ margin:15px 0; border:1px solid var(--line); border-radius:14px;
  background:#fff; overflow:hidden; }}
details.round > summary {{ cursor:pointer; padding:17px 20px; font-weight:800;
  background:#f8fafc; }}
.round-body {{ padding:6px 20px 20px; }}
.moderator {{ margin-top:15px; padding:16px; border-left:5px solid var(--mod);
  background:var(--mod-bg); border-radius:10px; }}
.badge {{ display:inline-block; margin-left:8px; padding:2px 9px; border-radius:999px;
  color:#fff; background:var(--mod); font-size:.78rem; vertical-align:middle; }}
.summary-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }}
.summary-card {{ padding:17px; box-shadow:none; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#111827; color:#e5e7eb;
  border-radius:12px; padding:18px; overflow:auto; }}
.judge {{ border-top:5px solid #111827; }}
@media (max-width:760px) {{ .two-column,.summary-grid {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body><main>
<header><h1>{company_name}</h1><p class="muted">MarketCouncil 종합 분석 · {generated_at}</p></header>
{self._render_debate(debate)}
<section class="section judge"><h2>Judge 종합 판단</h2>
<pre>{self._escape(analysis_data.get("judge_result", ""))}</pre></section>
<section class="section"><h2>원본 분석 자료</h2>
<details><summary>Bull 전체 분석</summary><pre>{self._escape(analysis_data.get("bull_result", ""))}</pre></details>
<details><summary>Bear 전체 분석</summary><pre>{self._escape(analysis_data.get("bear_result", ""))}</pre></details>
<details><summary>뉴스 민심 분석</summary><pre>{self._json(analysis_data.get("sentiment_result", {}))}</pre></details>
</section>
<p class="muted">토론 내용은 시각화 보고서에만 포함되며 Judge 입력에는 사용되지 않았습니다.</p>
</main></body></html>"""

    def _render_debate(self, debate: dict[str, Any]) -> str:
        if not debate:
            return '<section class="section"><h2>중재 토론</h2><p>토론 결과 없음</p></section>'
        agenda = debate.get("agenda", [])
        agenda_html = "".join(self._render_agenda(i, issue) for i, issue in enumerate(agenda, 1))
        rounds_html = "".join(
            self._render_round(round_data, agenda)
            for round_data in debate.get("rounds", [])
        )
        summary = debate.get("moderator_summary", {}) or {}
        return f"""<section class="section"><h2>중재 토론 핵심 시각화</h2>
<p class="muted">쟁점별 Bull/Bear 주장과 교차 반론을 비교합니다.</p>
{agenda_html}
<h3>라운드별 토론</h3>{rounds_html}
<h3>토론 결과</h3>
<div class="summary-grid">
{self._summary_card("합의 사항", summary.get("agreements", []))}
{self._summary_card("미해결 쟁점", summary.get("unresolved_issues", []))}
{self._summary_card("추가 필요 증거", summary.get("required_evidence", []))}
</div>
<div class="moderator"><strong>종료 이유</strong><p>{self._escape(debate.get("stop_reason", ""))}</p>
<strong>중재자 최종 요약</strong><p>{self._escape(summary.get("summary", ""))}</p></div>
</section>"""

    def _render_agenda(self, index: int, issue: dict[str, Any]) -> str:
        return f"""<article class="agenda"><h3>논제 {index}. {self._escape(issue.get("title", ""))}</h3>
<p class="question">{self._escape(issue.get("question", ""))}</p>
<div class="two-column"><div class="side bull"><h4>Bull 최초 주장</h4>
<p>{self._escape(issue.get("bull_claim", ""))}</p></div>
<div class="side bear"><h4>Bear 최초 주장</h4>
<p>{self._escape(issue.get("bear_claim", ""))}</p></div></div></article>"""

    def _render_round(
        self,
        round_data: dict[str, Any],
        agenda: list[dict[str, Any]],
    ) -> str:
        bull = round_data.get("bull_response", {}) or {}
        bear = round_data.get("bear_response", {}) or {}
        reviews = round_data.get("moderator_review", {}).get("issue_reviews", [])
        issue_ids = [str(item.get("issue_id", "")) for item in agenda]
        for turn in (bull, bear):
            for issue in turn.get("issues", []):
                issue_id = str(issue.get("issue_id", ""))
                if issue_id and issue_id not in issue_ids:
                    issue_ids.append(issue_id)
        issues_html = "".join(
            self._render_issue_pair(issue_id, bull, bear, reviews)
            for issue_id in issue_ids
        )
        round_number = self._escape(round_data.get("round", "?"))
        return f"""<details class="round" open><summary>{round_number}라운드</summary>
<div class="round-body">{issues_html}</div></details>"""

    def _render_issue_pair(
        self,
        issue_id: str,
        bull: dict[str, Any],
        bear: dict[str, Any],
        reviews: list[dict[str, Any]],
    ) -> str:
        bull_issue = self._find_issue(bull, issue_id)
        bear_issue = self._find_issue(bear, issue_id)
        review = next(
            (item for item in reviews if str(item.get("issue_id", "")) == issue_id),
            {},
        )
        return f"""<article class="issue"><h4>쟁점 · {self._escape(issue_id)}</h4>
<div class="two-column">
{self._turn_card("Bull", bull_issue, "bull")}
{self._turn_card("Bear", bear_issue, "bear")}
</div>
<div class="moderator"><strong>중재자 평가</strong>
<span class="badge">{self._escape(review.get("status", "미평가"))}</span>
<p>{self._escape(review.get("assessment", ""))}</p>
{self._question("Bull에게", review.get("question_for_bull", ""))}
{self._question("Bear에게", review.get("question_for_bear", ""))}</div></article>"""

    def _turn_card(self, role: str, issue: dict[str, Any], css_class: str) -> str:
        return f"""<div class="side {css_class}"><h4>{role}</h4>
<span class="label">상대 주장</span><p>{self._escape(issue.get("target_claim", ""))}</p>
<span class="label">반론</span><p>{self._escape(issue.get("response", ""))}</p>
<span class="label">반론 근거</span>{self._list(issue.get("evidence", []))}
<span class="label">인정하는 부분</span><p>{self._escape(issue.get("concession", ""))}</p>
<span class="label">추가 확인 필요</span><p>{self._escape(issue.get("missing_evidence", ""))}</p></div>"""

    @staticmethod
    def _find_issue(turn: dict[str, Any], issue_id: str) -> dict[str, Any]:
        return next(
            (
                item for item in turn.get("issues", [])
                if str(item.get("issue_id", "")) == issue_id
            ),
            {},
        )

    def _summary_card(self, title: str, items: list[Any]) -> str:
        return f'<div class="summary-card"><h4>{self._escape(title)}</h4>{self._list(items)}</div>'

    def _question(self, label: str, value: Any) -> str:
        if not value:
            return ""
        return f'<p><strong>{self._escape(label)}:</strong> {self._escape(value)}</p>'

    def _list(self, items: list[Any]) -> str:
        if not items:
            return "<p>없음</p>"
        return "<ul>" + "".join(f"<li>{self._escape(item)}</li>" for item in items) + "</ul>"

    @staticmethod
    def _escape(value: Any) -> str:
        return html.escape(str(value or ""))

    @staticmethod
    def _json(value: Any) -> str:
        return html.escape(json.dumps(value, ensure_ascii=False, indent=2, default=str))

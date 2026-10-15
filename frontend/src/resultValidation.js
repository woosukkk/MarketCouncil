const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string';
const optional = (value, check) => value == null || check(value);
const list = (value, check) => Array.isArray(value) && value.length <= 1000 && value.every(check);
const texts = (value, keys) => keys.every(key => optional(value[key], text));
const scalar = value => text(value) || (typeof value === 'number' && Number.isFinite(value));
const textList = value => list(value, text);

function evidence(value) {
  if (value === null || text(value)) return true; // Older results stored citations as text.
  return object(value) && texts(value, ['evidence_id','source_id','exact_quote','reason','title','source_type','source_url','published_at','source_page_url','context_text'])
    && optional(value.verified, item => typeof item === 'boolean') && optional(value.page_number, scalar);
}
function issue(value) {
  return object(value) && texts(value, ['issue_id','title','question','bull_claim','bear_claim','claim','warrant','qualifier','status','assessment','core_disagreement'])
    && optional(value.missing_evidence, item => text(item) || textList(item))
    && optional(value.evidence, item => list(item, evidence));
}
function response(value) {
  return object(value) && optional(value.issues, item => list(item, issue));
}
function review(value) {
  return object(value) && optional(value.issue_reviews, item => list(item, issue));
}
function round(value) {
  return object(value) && optional(value.round, scalar)
    && optional(value.bull_response, response) && optional(value.bear_response, response)
    && optional(value.moderator_review, review);
}
function summary(value) {
  return object(value) && texts(value, ['summary','headline','lead'])
    && ['agreements','unresolved_issues','required_evidence'].every(key => optional(value[key], textList));
}
function navigation(value) {
  return object(value) && texts(value, ['overview']) && optional(value.issues, item => list(item, issue));
}

// Check the fields the viewer consumes; keep optional legacy fields and unknown metadata.
export function validateResult(value) {
  if (!object(value) || !text(value.company_name) || !value.company_name.trim() || Array.from(value.company_name).length > 120
    || !list(value.rounds, round) || !texts(value, ['created_at','bull_analysis','bear_analysis'])
    || !optional(value.financial_data, item => object(item) && texts(item, ['ticker','price_date']))
    || !optional(value.agenda, item => list(item, issue)) || !optional(value.issue_statuses, item => list(item, issue))
    || !optional(value.moderator_summary, summary) || !optional(value.navigation, navigation)) {
    throw Error('분석 결과 형식이 올바르지 않아 열 수 없습니다. 원본 결과를 확인해 주세요.');
  }
  return value;
}

export function readResult(value) {
  if (object(value) && !Object.hasOwn(value, 'rounds') && (text(value.bull_analysis) || text(value.bear_analysis))) {
    return validateResult({...value, rounds:[]});
  }
  return validateResult(value);
}

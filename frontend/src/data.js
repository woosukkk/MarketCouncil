export const statuses = {OPEN:'추가 확인',CONTESTED:'견해 대립',RESOLVED:'쟁점 해소',STALEMATE:'교착',UNKNOWN:'자료 부족'};
export function safeUrl(value) {
  try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : null; } catch { return null; }
}
export function dateLabel(value) { return value ? String(value).slice(0, 10).replaceAll('-', '.') : '날짜 미상'; }
export function issueStatus(data, id) {
  return (data.navigation?.issues || []).find(x => x.issue_id === id)?.status || (data.issue_statuses || []).find(x => x.issue_id === id)?.status || 'UNKNOWN';
}
export function evidenceCount(data) {
  return (data.rounds || []).reduce((n,r) => n + ['bull_response','bear_response'].reduce((m,s) => m + (r[s]?.issues || []).reduce((v,i) => v + (i.evidence || []).length,0),0),0);
}
export function filterSessions(sessions, query) {
  const q = query.trim().toLowerCase();
  return sessions.filter(s => `${s.company_name} ${s.created_at} ${s.summary}`.toLowerCase().includes(q));
}

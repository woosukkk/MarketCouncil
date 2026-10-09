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

export function resultsUrl(filename) {
  const base = (import.meta.env?.VITE_RESULTS_BASE_URL || '/data').replace(/\/$/, '');
  if (!/^(index|[a-f0-9]{16}(?:-[a-f0-9]{16})?)\.json$/.test(filename)) throw Error('Invalid result filename');
  return `${base}/${filename}`;
}
export function usedSources(data) {
  const sources = new Map();
  for (const [r, round] of (data.rounds || []).entries()) {
    for (const side of ['bull', 'bear']) {
      for (const issue of round[`${side}_response`]?.issues || []) {
        for (const item of issue.evidence || []) {
          if (!item || typeof item !== 'object') continue;
          const key = item.source_id || item.source_url || item.title || `${r}-${side}-${issue.issue_id}-${item.evidence_id}`;
          if (!sources.has(key)) sources.set(key, {...item, uses: [], quotes: []});
          const source = sources.get(key);
          const usage = `Round ${round.round || r+1} · ${side.toUpperCase()} · ${issue.issue_id || '의제 미상'}`;
          if (!source.uses.includes(usage)) source.uses.push(usage);
          if (item.exact_quote && !source.quotes.includes(item.exact_quote)) source.quotes.push(item.exact_quote);
        }
      }
    }
  }
  return [...sources.values()];
}

export const resultKey = id => id.replace(/-[a-f0-9]{16}$/, '');

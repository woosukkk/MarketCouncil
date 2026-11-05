import {koreaToday} from './data.js';

const dayMs = 86400000;
const koreaDate = new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Seoul', year:'numeric', month:'2-digit', day:'2-digit'});

function analysisDay(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:[T ]|$)/.test(value)) return null;
  const date = value.slice(0, 10);
  const day = new Date(date + 'T00:00:00Z');
  if (!Number.isFinite(+day) || day.toISOString().slice(0, 10) !== date) return null;
  // Legacy timestamps without an offset already describe a local calendar date.
  if (value.length === 10 || !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)) return date;
  const instant = new Date(value);
  return Number.isFinite(+instant) ? koreaDate.format(instant) : null;
}

export function groupLibraryPeriods(rows, today = koreaToday()) {
  const recent = [], older = new Map();
  for (const row of rows) {
    const date = analysisDay(row.created_at);
    const age = date ? (Date.parse(today) - Date.parse(date)) / dayMs : null;
    if (age !== null && age < 30) {
      recent.push(row);
      continue;
    }
    const year = date?.slice(0, 4);
    const month = date ? Number(date.slice(5, 7)) : null;
    let kind, period;
    if (!date) kind = 'undated';
    else if (age < 90) { kind = 'month'; period = month; }
    else if (age < 180) { kind = 'quarter'; period = Math.ceil(month / 3); }
    else if (age < 365) { kind = 'half'; period = month <= 6 ? 1 : 2; }
    else kind = 'year';
    const id = `${kind}-${year ?? ''}-${period ?? ''}`;
    if (!older.has(id)) older.set(id, {id, kind, year, period, latest:date ?? '', rows:[]});
    const group = older.get(id);
    if (date && date > group.latest) group.latest = date;
    group.rows.push(row);
  }
  return {recent, older:[...older.values()].sort((a, b) => b.latest.localeCompare(a.latest))};
}

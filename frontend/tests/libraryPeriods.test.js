import test from 'node:test';
import assert from 'node:assert/strict';
import {groupLibraryPeriods} from '../src/libraryPeriods.js';

test('Korean date cutoffs put each analysis in one bucket and preserve the record', () => {
  const rows = [
    {id:'29', created_at:'2026-10-06T15:00:00Z'},
    {id:'30', created_at:'2026-10-06T14:59:59Z'},
    {id:'89', created_at:'2026-08-08'},
    {id:'90', created_at:'2026-08-07'},
    {id:'179', created_at:'2026-05-10'},
    {id:'180', created_at:'2026-05-09'},
    {id:'364', created_at:'2025-11-06'},
    {id:'365', created_at:'2025-11-05'},
    {id:'unknown', created_at:'2026-02-30'},
  ].map(Object.freeze);
  const {recent, older} = groupLibraryPeriods(Object.freeze(rows), '2026-11-05');
  assert.deepEqual(recent, [rows[0]]);
  assert.deepEqual(older.map(g => [g.id, g.rows.map(row => row.id)]), [
    ['month-2026-10', ['30']], ['month-2026-8', ['89']], ['quarter-2026-3', ['90']],
    ['quarter-2026-2', ['179']], ['half-2026-1', ['180']], ['half-2025-2', ['364']],
    ['year-2025-', ['365']], ['undated--', ['unknown']],
  ]);
  assert.equal(older[0].rows[0], rows[1]);
});

test('past groups start collapsed and search renders a flat list', async () => {
  const [{createServer}, {createElement}, {renderToStaticMarkup}] = await Promise.all([
    import('vite'), import('react'), import('react-dom/server'),
  ]);
  const server = await createServer({envFile:false, configFile:false, logLevel:'silent', server:{middlewareMode:true, hmr:false}});
  try {
    const {default:LibraryPeriods} = await server.ssrLoadModule('/src/LibraryPeriods.jsx');
    const rows = [{id:'one', created_at:'2020-12-01'}, {id:'two', created_at:'2020-01-02'}];
    const renderCard = row => createElement('button', {key:row.id}, row.id);
    const render = searching => renderToStaticMarkup(createElement(LibraryPeriods, {rows, searching, renderCard}));
    const grouped = render(false);
    assert.equal((grouped.match(/<details /g) || []).length, 1);
    assert.doesNotMatch(grouped, /<details[^>]+open/);
    assert.match(grouped, /2020년/);
    assert.match(grouped, /분석 2건/);
    assert.doesNotMatch(render(true), /<details/);
    assert.match(render(true), /<button>one<\/button><button>two<\/button>/);
  } finally {
    await server.close();
  }
});

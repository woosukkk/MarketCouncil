import test from 'node:test';
import assert from 'node:assert/strict';
import {companyRelations,relationNodes,relationsFor} from './companyRelations.js';

test('relations stay within known entities and keep facts separate from scenarios',()=>{
 const ids=new Set(relationNodes.map(node=>node.id));
 assert.equal(new Set(companyRelations.map(row=>row.id)).size,companyRelations.length);
 for(const row of companyRelations){
  assert.ok(ids.has(row.from)&&ids.has(row.to)&&row.from!==row.to);
  assert.equal(new URL(row.url).protocol,'https:');
  for(const key of ['fact','upside','downside','needed'])assert.ok(row[key].length===2&&row[key].every(Boolean));
 }
 assert.deepEqual(relationsFor('unknown'),[]);
 assert.ok(relationsFor('AAPL').every(row=>row.to==='AAPL'||row.from==='AAPL'));
 assert.ok(relationsFor('AAPL').every(row=>row.historical&&row.period==='FY2023'));
});

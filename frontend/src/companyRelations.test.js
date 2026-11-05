import test from 'node:test';
import assert from 'node:assert/strict';
import {companyRelations,relationNodes,relationsAsOf,relationsFor} from './companyRelations.js';

test('relations stay within known entities and keep facts separate from scenarios',()=>{
 const ids=new Set(relationNodes.map(node=>node.id));
 assert.equal(new Set(companyRelations.map(row=>row.id)).size,companyRelations.length);
 for(const row of companyRelations){
  assert.ok(ids.has(row.from)&&ids.has(row.to)&&row.from!==row.to);
  assert.ok(row.evidence.length>0,`${row.id} lacks primary evidence`);
  for(const item of row.evidence){
   const url=new URL(item.url);
   assert.equal(url.protocol,'https:');
   assert.ok(['www.apple.com','www.supplychainreports.apple','news.samsung.com','www.navercorp.com','nvidianews.nvidia.com'].includes(url.hostname));
   assert.ok(item.source && item.locator && item.excerpt && item.excerpt.split(/\s+/).length<=25);
   for(const key of ['data','limit'])assert.ok(item[key].length===2&&item[key].every(Boolean));
   const date=item.locator.match(/^\d{4}-\d{2}-\d{2}/)?.[0];
   if(date)assert.ok(date<=relationsAsOf);
   else assert.match(item.locator,/^FY2023 · PDF p\.\d+$/);
  }
  for(const key of ['fact','upside','downside','needed'])assert.ok(row[key].length===2&&row[key].every(Boolean));
 }
 assert.deepEqual(relationsFor('unknown'),[]);
 assert.ok(relationsFor('AAPL').every(row=>row.to==='AAPL'||row.from==='AAPL'));
 const apple=relationsFor('AAPL');
 const oldSupplier=apple.find(row=>row.id==='apple-hynix');
 assert.ok(oldSupplier.historical&&oldSupplier.period==='FY2023');
 assert.equal(new URL(oldSupplier.evidence[0].url).hash,'#page=20');
 const austin=apple.find(row=>row.id==='apple-samsung');
 assert.equal(austin.period,'2025-08-06');
 assert.ok(austin.evidence[0].excerpt.includes('Austin'));
 assert.equal(new URL(austin.evidence[1].url).hash,'#page=19');
});

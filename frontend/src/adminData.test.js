import {test} from 'node:test';
import assert from 'node:assert/strict';
import {measurementReport,monitoringSummary,metricText} from './adminData.js';
const base={schema_version:1,kind:'monitoring',id:'11111111-1111-4111-8111-111111111111',recorded_at:'2026-10-10T00:00:00Z',label:'삼성전자',scope:'analysis',status:'success',metrics:{duration_ms:10,cpu_ms:5}};
test('measurement import strips secrets, raw text and unsupported fields',()=>{
 const clean=measurementReport({...base,OPENAI_API_KEY:'secret',prompt:'private',environment:{os:'Windows',email:'private'},metrics:{...base.metrics,private:123}});
 assert.equal(clean.metrics.duration_ms,10);assert.equal(JSON.stringify(clean).includes('private'),false);assert.equal(JSON.stringify(clean).includes('secret'),false);
});
test('invalid metrics and fake incomplete benchmark records are rejected',()=>{
 assert.throws(()=>measurementReport({...base,metrics:{duration_ms:-1}}));
 assert.throws(()=>measurementReport({...base,metrics:{duration_ms:Infinity}}));
 assert.throws(()=>measurementReport({...base,kind:'rag'}));
 assert.equal(metricText(undefined),'미측정');
});
test('summary excludes HTTP probes and never fabricates rates for no samples',()=>{
 assert.equal(monitoringSummary([]).successRate,null);
 const result=monitoringSummary([base,{...base,status:'failed'},{...base,scope:'web_http'}]);
 assert.equal(result.count,2);assert.equal(result.successRate,.5);
});

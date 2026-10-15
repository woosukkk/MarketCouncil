import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateResult,readResult} from './resultValidation.js';
import {prepareResult} from './resultUpload.js';
const fixture=JSON.parse(readFileSync(new URL('../tests/result-validation-cases.json',import.meta.url),'utf8'));
for(const row of fixture.cases)test(`result shape: ${row.name}`,()=>{
 const value=row.result??{...structuredClone(fixture.base),...row.fields};
 if(row.valid){assert.equal(validateResult(value),value);assert.doesNotThrow(()=>prepareResult(JSON.stringify(value)));}
 else {assert.throws(()=>validateResult(value));assert.throws(()=>prepareResult(JSON.stringify(value)));}
});
test('render collections have a bounded item count',()=>{
 assert.throws(()=>validateResult({company_name:'Example',rounds:Array.from({length:1001},()=>({}))}));
});
test('old text-only archives stay readable without weakening new uploads',()=>{
 const legacy={company_name:'Example',bull_analysis:'Bull',bear_analysis:'Bear'};
 assert.deepEqual(readResult(legacy).rounds,[]);
 assert.ok(!('rounds' in legacy));
 assert.throws(()=>prepareResult(JSON.stringify(legacy)));
 assert.throws(()=>readResult({company_name:'Example',rounds:null,bull_analysis:'Bull'}));
});

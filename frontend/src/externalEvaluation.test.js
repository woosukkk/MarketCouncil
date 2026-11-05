import test from 'node:test';
import assert from 'node:assert/strict';
import {externalEvaluation,externalMetrics} from './externalEvaluation.js';
const fixture=()=>{
 const cases=[{case_id:'1'.repeat(16),faithfulness:1,context_precision:null,context_recall:.5,factual_correctness:null}];
 const metrics={case_count:1};for(const key of externalMetrics){metrics[key]=cases[0][key];metrics[key+'_count']=cases[0][key]===null?0:1;}
 return {schema_version:1,kind:'rag',scope:'external_rag',status:'success',id:'12345678-1234-1234-1234-123456789abc',recorded_at:'2026-11-05T00:00:00Z',dataset_hash:'1'.repeat(64),settings:{framework_version:'0.4.0',dataset_name:'unit-fixture',dataset_version:'v1',evaluator_model:'fixture-only',reference_origin:'synthetic',metric_config_hash:'2'.repeat(64)},metrics,cases};
};
test('external scores preserve missing data, reject forged means and strip raw fields',()=>{
 const raw=fixture();raw.prompt='private';const clean=externalEvaluation(raw);
 assert.equal(clean.metrics.context_precision,null);assert.equal(clean.metrics.context_precision_count,0);assert.ok(!Object.hasOwn(clean,'prompt'));
 raw.metrics.faithfulness=.5;assert.throws(()=>externalEvaluation(raw));
 const negative=fixture();negative.cases[0].faithfulness=-1;assert.throws(()=>externalEvaluation(negative));
 const duplicate=fixture();duplicate.cases.push({...duplicate.cases[0]});assert.throws(()=>externalEvaluation(duplicate));
});

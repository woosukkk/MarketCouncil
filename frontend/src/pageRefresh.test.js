import {test} from 'node:test';
import assert from 'node:assert/strict';
import {watchPageRefresh} from './pageRefresh.js';

test('returning to the visible page refreshes data and cleanup removes listeners',()=>{
 const targetWindow=new EventTarget(),targetDocument=new EventTarget();
 targetDocument.visibilityState='visible';
 let refreshes=0;
 const stop=watchPageRefresh(()=>refreshes++,targetWindow,targetDocument);
 targetWindow.dispatchEvent(new Event('focus'));
 assert.equal(refreshes,1);
 targetDocument.visibilityState='hidden';
 targetWindow.dispatchEvent(new Event('focus'));
 targetDocument.dispatchEvent(new Event('visibilitychange'));
 assert.equal(refreshes,1);
 targetDocument.visibilityState='visible';
 targetDocument.dispatchEvent(new Event('visibilitychange'));
 assert.equal(refreshes,2);
 stop();
 targetWindow.dispatchEvent(new Event('focus'));
 targetDocument.dispatchEvent(new Event('visibilitychange'));
 assert.equal(refreshes,2);
});

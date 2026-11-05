import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {parseSync} from 'rolldown/utils';
import {english} from '../src/messages.en.js';
import {LANGUAGE_KEY,initialLanguage,rememberLanguage,translate,withLanguage} from '../src/language.js';

test('explicit supported language overrides storage, otherwise Korean is the safe default',()=>{
 const storage={getItem:key=>{assert.equal(key,LANGUAGE_KEY);return 'en'}};
 assert.equal(initialLanguage('?lang=ko',storage),'ko');
 assert.equal(initialLanguage('?lang=en'),'en');
 assert.equal(initialLanguage('?lang=fr',storage),'en');
 assert.equal(initialLanguage('?lang=__proto__',{getItem:()=>'<script>'}),'ko');
 assert.equal(initialLanguage(''),'ko');
});

test('blocked preference storage cannot break navigation or language selection',()=>{
 const blocked={getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}};
 assert.equal(initialLanguage('',blocked),'ko');
 assert.equal(initialLanguage('?lang=en',blocked),'en');
 assert.doesNotThrow(()=>rememberLanguage(blocked,'en'));
 const writes=[];rememberLanguage({setItem:(...args)=>writes.push(args)},'en');
 rememberLanguage({setItem:()=>assert.fail('unsupported language written')},'fr');
 assert.deepEqual(writes,[[LANGUAGE_KEY,'en']]);
});

test('language URLs preserve view, share, callback fragments and unrelated parameters',()=>{
 const input='/app?view=my&share=1234-test-token&next=a%2Fb#access_token=offline-token&refresh_token=offline-refresh';
 const localized=withLanguage(input,'en'),url=new URL(localized,'https://example.test');
 assert.equal(url.searchParams.get('view'),'my');
 assert.equal(url.searchParams.get('share'),'1234-test-token');
 assert.equal(url.searchParams.get('next'),'a/b');
 assert.equal(url.searchParams.get('lang'),'en');
 assert.equal(url.hash,new URL(input,'https://example.test').hash);
 assert.equal(new URL(withLanguage(localized,'ko'),'https://example.test').searchParams.has('lang'),false);
 for(const path of ['https://other.example/file.pdf','//other.example/file.pdf','#preview'])assert.equal(withLanguage(path,'en'),path);
});

test('translations handle whitespace, counters and interpolation without changing saved text',()=>{
 assert.equal(translate(' 로그인 ','en'),' Sign in ');
 assert.equal(translate('개','en'),'');
 assert.equal(translate(' · {0}쪽','en',{0:4}),' · p. 4');
 assert.equal(translate(' · {0}쪽','ko',{0:4}),' · 4쪽');
 const original='삼성전자: 실제 주장의 원문과 인용을 보존합니다. <not-html>';
 assert.equal(translate(original,'en'),original);
 assert.equal(translate('로그인','ko'),'로그인');
 assert.equal(translate(null,'en'),null);
 assert.equal(translate(0,'en'),0);
 assert.equal(translate('기록을 저장하지 못했습니다. 관리자 권한을 확인하세요. (23503)','en'),'Unable to save the record. Check your admin access. (23503)');
});

test('all supplied English messages and placeholders are complete',()=>{
 assert.ok(Object.keys(english).length>400);
 for(const [key,value] of Object.entries(english)){
  assert.equal(typeof value,'string',key);
  assert.equal(/[가-힣]/.test(value),false,key);
  assert.deepEqual((key.match(/\{\w+\}/g)||[]).sort(),(value.match(/\{\w+\}/g)||[]).sort(),key);
 }
});

test('every fixed Korean UI label and surfaced validator message has an English entry',async()=>{
 const files=['main.jsx','Landing.jsx','Account.jsx','Discussions.jsx','GettingStarted.jsx','Admin.jsx','data.js','adminData.js','resultUpload.js','resultValidation.js'];
 const visit=node=>{
  if(!node||typeof node!=='object')return;
  if(Array.isArray(node)){node.forEach(visit);return;}
  if(node.type==='Literal'&&typeof node.value==='string'&&/[가-힣]/.test(node.value))assert.ok(Object.hasOwn(english,node.value.trim()),node.value);
  if(node.type==='JSXText')assert.equal(/[가-힣]/.test(node.value),false,'untranslated JSX: '+node.value);
  for(const [key,value] of Object.entries(node))if(!['loc','comments','range'].includes(key))visit(value);
 };
 for(const file of files){const source=await readFile(new URL('../src/'+file,import.meta.url),'utf8');const result=parseSync(file,source);assert.deepEqual(result.errors,[],file);visit(result.program);}
});

test('actual public, account and admin components render English through shared context',async()=>{
 const {createServer}=await import('vite');
 const server=await createServer({root:fileURLToPath(new URL('../',import.meta.url)),envFile:false,configFile:false,logLevel:'silent',server:{middlewareMode:true,hmr:false}});
 try{
  const {LanguageContext,LanguageSwitch}=await server.ssrLoadModule('/src/Language.jsx');
  const defaultText=renderToStaticMarkup(createElement(LanguageContext.Consumer,null,value=>createElement('span',null,value.t(' · {0}쪽',{0:4}))));
  assert.match(defaultText,/ · 4쪽/);
  const {default:Landing}=await server.ssrLoadModule('/src/Landing.jsx');
  const {default:GettingStarted}=await server.ssrLoadModule('/src/GettingStarted.jsx');
  const {Login,MyPage}=await server.ssrLoadModule('/src/Account.jsx');
  const {default:Discussions}=await server.ssrLoadModule('/src/Discussions.jsx');
  const {default:Admin}=await server.ssrLoadModule('/src/Admin.jsx');
  const render=(Component,props={},locale='en')=>renderToStaticMarkup(createElement(LanguageContext.Provider,{value:{locale,t:(text,values)=>translate(text,locale,values),setLocale:()=>{}}},createElement(Component,props)));
  const landing=render(Landing,{navigate:()=>{}});
  assert.match(landing,/Better decisions/);assert.match(landing,/different perspective/);assert.match(landing,/href="\/app\?lang=en"/);
  assert.match(landing,/aria-label="Interface language"/);assert.match(landing,/lang="en" aria-pressed="true"/);
  assert.match(render(Landing,{navigate:()=>{}},'ko'),/좋은 판단은/);
  assert.match(render(LanguageSwitch),/EN/);
  for(const [Component,props,expected] of [[GettingStarted,{},'Start your own research'],[Login,{},'Continue with email'],[MyPage,{},'My research'],[Discussions,{},'Shared discussions'],[Admin,{allowed:false,checking:false},'official editor'],[Admin,{allowed:true,checking:false},'Service performance and evidence quality']]){
   const html=render(Component,props);assert.ok(html.includes(expected),expected);assert.equal(/[가-힣]/.test(html),false,expected);
  }
 }finally{await server.close();}
});

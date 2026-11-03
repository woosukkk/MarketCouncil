import {english} from './messages.en.js';

export const LANGUAGE_KEY='marketcouncil.language';
export const isLanguage=value=>value==='ko'||value==='en';

export function initialLanguage(search='',storage=null){
 const requested=new URLSearchParams(search).get('lang');
 if(isLanguage(requested))return requested;
 try{const saved=storage?.getItem(LANGUAGE_KEY);if(isLanguage(saved))return saved;}catch{}
 return 'ko';
}

export function rememberLanguage(storage,locale){
 if(!isLanguage(locale))return;
 try{storage?.setItem(LANGUAGE_KEY,locale);}catch{}
}

export function withLanguage(path,locale){
 if(typeof path!=='string'||!path.startsWith('/')||path.startsWith('//'))return path;
 const url=new URL(path,'https://marketcouncil.invalid');
 if(locale==='en')url.searchParams.set('lang','en');else url.searchParams.delete('lang');
 return url.pathname+url.search+url.hash;
}

export function translate(text,locale='ko',values={}){
 if(typeof text!=='string')return text;
 const key=text.trim();
 let result=text;
 if(locale==='en'&&Object.hasOwn(english,key)){
  const leading=text.match(/^\s*/)[0],trailing=text.match(/\s*$/)[0];
  result=leading+english[key]+trailing;
 }else if(locale==='en'){
  const prefix='기록을 저장하지 못했습니다. 관리자 권한을 확인하세요. (';
  if(text.startsWith(prefix)&&text.endsWith(')'))result=english[prefix]+translate(text.slice(prefix.length,-1),locale)+')';
 }
 return result.replace(/\{([a-zA-Z0-9_]+)\}/g,(match,name)=>Object.hasOwn(values,name)?String(values[name]):match);
}

import React,{createContext,useCallback,useContext,useEffect,useState} from 'react';
import {initialLanguage,isLanguage,rememberLanguage,translate,withLanguage} from './language.js';

export const LanguageContext=createContext({locale:'ko',t:(text,values)=>translate(text,'ko',values),setLocale:()=>{}});
export const useLanguage=()=>useContext(LanguageContext);

export function LanguageProvider({children}){
 const [locale,updateLocale]=useState(()=>{
  let storage=null;try{storage=window.localStorage;}catch{}
  return initialLanguage(window.location.search,storage);
 });
 useEffect(()=>{
  const restore=()=>{let storage=null;try{storage=window.localStorage;}catch{}updateLocale(initialLanguage(window.location.search,storage));};
  window.addEventListener('popstate',restore);return()=>window.removeEventListener('popstate',restore);
 },[]);
 const t=useCallback((text,values)=>translate(text,locale,values),[locale]);
 const setLocale=useCallback(next=>{
  if(!isLanguage(next))return;
  updateLocale(next);
  try{const current=location.pathname+location.search+location.hash;history.replaceState(history.state,'',withLanguage(current,next));}catch{}
 },[]);
 useEffect(()=>{
  document.documentElement.lang=locale;
  document.title=locale==='en'?'MarketCouncil · Investment research':'MarketCouncil · 투자 리서치';
  try{rememberLanguage(window.localStorage,locale);}catch{}
 },[locale]);
 return <LanguageContext.Provider value={{locale,t,setLocale}}>{children}</LanguageContext.Provider>;
}

export function LanguageSwitch(){
 const {locale,t,setLocale}=useLanguage();
 return <div className="language-switch" role="group" aria-label={t('표시 언어')}>
  <button type="button" lang="ko" aria-pressed={locale==='ko'} onClick={()=>setLocale('ko')}>한국어</button>
  <button type="button" lang="en" aria-pressed={locale==='en'} onClick={()=>setLocale('en')}>EN</button>
 </div>;
}

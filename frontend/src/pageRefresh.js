export function watchPageRefresh(refresh, targetWindow=window, targetDocument=document) {
  const visible=()=>{if(targetDocument.visibilityState!=='hidden')refresh();};
  targetWindow.addEventListener('focus',visible);
  targetDocument.addEventListener('visibilitychange',visible);
  return ()=>{
    targetWindow.removeEventListener('focus',visible);
    targetDocument.removeEventListener('visibilitychange',visible);
  };
}

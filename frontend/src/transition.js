import {flushSync} from 'react-dom';

export function transition(update) {
  if (document.startViewTransition && !matchMedia('(prefers-reduced-motion: reduce)').matches) document.startViewTransition(() => flushSync(update));
  else update();
}

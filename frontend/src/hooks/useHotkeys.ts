import { useEffect } from 'react';

interface HotkeyMap {
  'ctrl+enter'?: () => void;
  escape?: () => void;
  a?: () => void;
  d?: () => void;
  arrowright?: () => void;
}

export function useHotkeys(map: HotkeyMap, deps: unknown[] = []) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';

      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        map['ctrl+enter']?.();
      }
      if (e.key === 'Escape') {
        map.escape?.();
      }
      if (!isInput) {
        if (e.key === 'a') { e.preventDefault(); map.a?.(); }
        if (e.key === 'd') { e.preventDefault(); map.d?.(); }
        if (e.key === 'ArrowRight') { e.preventDefault(); map.arrowright?.(); }
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

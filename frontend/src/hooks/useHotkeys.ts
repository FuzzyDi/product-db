import { useEffect } from 'react';

interface HotkeyMap {
  'ctrl+enter'?: () => void;
  escape?: () => void;
}

export function useHotkeys(map: HotkeyMap, deps: unknown[] = []) {
  useEffect(() => {
    function handler(e: KeyboardEvent) {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        map['ctrl+enter']?.();
      }
      if (e.key === 'Escape') {
        map.escape?.();
      }
    }
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

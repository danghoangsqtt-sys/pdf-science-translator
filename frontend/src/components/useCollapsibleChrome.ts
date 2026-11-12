import { useCallback, useState } from 'react';

const COLLAPSED_KEY = 'pdftranslate.toolbarCollapsed';

function readCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_KEY) === '1';
  } catch {
    return false;
  }
}

export interface CollapsibleChrome {
  /** Whether the toolbar is collapsed right now. */
  hidden: boolean;
  /** False while `force` keeps the toolbar open, so the toggle has no effect. */
  canCollapse: boolean;
  toggle: () => void;
  expand: () => void;
}

/**
 * The top toolbar collapses and expands only when the reader asks, and the
 * choice is remembered. `force` (nothing open yet, a job being cancelled)
 * keeps it open without changing the remembered choice.
 */
export function useCollapsibleChrome(force: boolean): CollapsibleChrome {
  const [collapsed, setCollapsedState] = useState(readCollapsed);

  const setCollapsed = useCallback((next: boolean) => {
    setCollapsedState(next);
    try {
      window.localStorage.setItem(COLLAPSED_KEY, next ? '1' : '0');
    } catch {
      // Opens expanded next launch; nothing else depends on it.
    }
  }, []);

  const toggle = useCallback(() => setCollapsed(!collapsed), [collapsed, setCollapsed]);
  const expand = useCallback(() => setCollapsed(false), [setCollapsed]);

  return { hidden: collapsed && !force, canCollapse: !force, toggle, expand };
}

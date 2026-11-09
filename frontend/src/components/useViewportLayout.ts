import { useEffect, useState } from 'react';

/**
 * Below this window width two portrait PDFs side by side are each narrower
 * than about 560 px and hard to read, so one pane is shown at a time.
 * A 5:4 or 4:3 screen that is wide enough keeps both panes, just taller.
 */
export const SIDE_BY_SIDE_MIN_WIDTH = 1200;

export type ComparisonMode = 'source' | 'translated' | 'both';

export interface ViewportLayout {
  width: number;
  height: number;
  /** Whether two panes fit side by side by default. */
  sideBySide: boolean;
}

export const layoutFor = (width: number, height: number): ViewportLayout => ({
  width, height, sideBySide: width >= SIDE_BY_SIDE_MIN_WIDTH,
});

/** The window size, updated at most once per animation frame while resizing. */
export function useViewportLayout(): ViewportLayout {
  const [layout, setLayout] = useState(() => layoutFor(window.innerWidth, window.innerHeight));
  useEffect(() => {
    let frame: number | null = null;
    const update = () => {
      if (frame !== null) return;
      frame = requestAnimationFrame(() => {
        frame = null;
        setLayout((old) => {
          const next = layoutFor(window.innerWidth, window.innerHeight);
          return old.width === next.width && old.height === next.height ? old : next;
        });
      });
    };
    window.addEventListener('resize', update);
    return () => {
      window.removeEventListener('resize', update);
      if (frame !== null) cancelAnimationFrame(frame);
    };
  }, []);
  return layout;
}

const MODE_KEY = 'pdftranslate.comparisonMode';

/** The mode the user picked by hand, if any. Storage may be unavailable. */
export function readStoredMode(): ComparisonMode | null {
  try {
    const value = window.localStorage.getItem(MODE_KEY);
    return value === 'source' || value === 'translated' || value === 'both' ? value : null;
  } catch {
    return null;
  }
}

export function storeMode(mode: ComparisonMode): void {
  try {
    window.localStorage.setItem(MODE_KEY, mode);
  } catch {
    // A forgotten preference only means the default layout next time.
  }
}

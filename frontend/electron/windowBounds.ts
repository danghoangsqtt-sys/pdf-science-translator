/**
 * Where the main window opens, from the screens actually attached.
 *
 * Kept free of Electron imports so it runs under `node --test`. A projector
 * at 1024x768 or 800x600 has a work area smaller than the 1360x880 the app
 * used to ask for, so the window spilled off screen with its buttons hidden.
 */

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface SavedWindow {
  bounds: Rect;
  maximized: boolean;
}

export interface WindowPlan {
  bounds: Rect;
  minWidth: number;
  minHeight: number;
  maximize: boolean;
}

export const PREFERRED_SIZE = { width: 1360, height: 880 };
export const MIN_SIZE = { width: 760, height: 540 };
// Below this work area the window opens maximized: every pixel goes to the PDF.
export const SMALL_WORK_AREA = { width: 1100, height: 700 };
const WORK_AREA_SHARE = 0.92;

function overlap(a: Rect, b: Rect): number {
  const width = Math.min(a.x + a.width, b.x + b.width) - Math.max(a.x, b.x);
  const height = Math.min(a.y + a.height, b.y + b.height) - Math.max(a.y, b.y);
  return width > 0 && height > 0 ? width * height : 0;
}

/** The work area holding most of `bounds`, or null when it is on no screen. */
export function displayFor(bounds: Rect, workAreas: Rect[]): Rect | null {
  let best: Rect | null = null;
  let bestArea = 0;
  for (const area of workAreas) {
    const shared = overlap(bounds, area);
    if (shared > bestArea) {
      best = area;
      bestArea = shared;
    }
  }
  // Less than a third on screen means the title bar may be unreachable.
  return best && bestArea >= (bounds.width * bounds.height) / 3 ? best : null;
}

export function minimumFor(workArea: Rect): { minWidth: number; minHeight: number } {
  return {
    minWidth: Math.min(MIN_SIZE.width, workArea.width),
    minHeight: Math.min(MIN_SIZE.height, workArea.height),
  };
}

/** Fit `bounds` inside `workArea`, keeping its size where it fits. */
export function clampInto(bounds: Rect, workArea: Rect): Rect {
  const width = Math.min(bounds.width, workArea.width);
  const height = Math.min(bounds.height, workArea.height);
  const x = Math.min(Math.max(bounds.x, workArea.x), workArea.x + workArea.width - width);
  const y = Math.min(Math.max(bounds.y, workArea.y), workArea.y + workArea.height - height);
  return { x: Math.round(x), y: Math.round(y), width: Math.round(width), height: Math.round(height) };
}

/** The default window for one screen: preferred size, never past 92% of it, centred. */
export function centredIn(workArea: Rect): Rect {
  const { minWidth, minHeight } = minimumFor(workArea);
  const width = Math.max(minWidth, Math.min(PREFERRED_SIZE.width, Math.round(workArea.width * WORK_AREA_SHARE)));
  const height = Math.max(minHeight, Math.min(PREFERRED_SIZE.height, Math.round(workArea.height * WORK_AREA_SHARE)));
  return {
    x: Math.round(workArea.x + (workArea.width - width) / 2),
    y: Math.round(workArea.y + (workArea.height - height) / 2),
    width,
    height,
  };
}

export function isSmall(workArea: Rect): boolean {
  return workArea.width < SMALL_WORK_AREA.width || workArea.height < SMALL_WORK_AREA.height;
}

/**
 * Reuse the last window when it is still on an attached screen (a projector
 * that was unplugged is not); otherwise open centred on `current`.
 */
export function planWindow(current: Rect, saved: SavedWindow | null, workAreas: Rect[]): WindowPlan {
  const home = saved ? displayFor(saved.bounds, workAreas) : null;
  if (saved && home) {
    return {
      bounds: clampInto(saved.bounds, home),
      ...minimumFor(home),
      maximize: saved.maximized || isSmall(home),
    };
  }
  return { bounds: centredIn(current), ...minimumFor(current), maximize: isSmall(current) };
}

/** Accept only a well-formed saved state; anything else means "no saved state". */
export function parseSavedWindow(value: unknown): SavedWindow | null {
  if (!value || typeof value !== 'object') return null;
  const { bounds, maximized } = value as { bounds?: Partial<Rect>; maximized?: unknown };
  if (!bounds) return null;
  const numbers = [bounds.x, bounds.y, bounds.width, bounds.height];
  if (!numbers.every((n) => typeof n === 'number' && Number.isFinite(n))) return null;
  if ((bounds.width as number) < 100 || (bounds.height as number) < 100) return null;
  return { bounds: bounds as Rect, maximized: maximized === true };
}

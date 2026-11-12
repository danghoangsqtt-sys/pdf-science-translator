export interface ReadingPosition {
  page: number;
  offset: number;
  x: number;
}
export const clampScale = (value: number): number =>
  Math.min(4, Math.max(0.4, Number(value.toFixed(2))));

export type ZoomMode = 'fit' | 'custom';

/**
 * The scale at which the widest page fills the pane. `available` is the
 * pane's inner width (scrollbar excluded) and `padding` its horizontal padding.
 */
export function fitWidthScale(available: number, pageWidths: ReadonlyArray<number>, padding = 32): number {
  const widest = Math.max(0, ...pageWidths);
  const room = available - padding;
  if (widest <= 0 || room <= 0) return 1;
  // Round down: clampScale rounds to two decimals, and rounding up makes the
  // page a few pixels wider than the pane and brings back a sideways scrollbar.
  return clampScale(Math.floor((room / widest) * 100) / 100);
}

// Page-relative positions avoid drift when page sizes or viewport widths differ.
export function pageAtOffset(
  pages: ReadonlyArray<{ top: number; height: number }>, y: number,
): Pick<ReadingPosition, 'page' | 'offset'> {
  if (!pages.length) return { page: 1, offset: 0 };
  let low = 0;
  let high = pages.length - 1;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (pages[middle].top <= y) low = middle;
    else high = middle - 1;
  }
  const page = pages[low];
  // Keep offsets just beyond the page while the viewport is in its gutter.
  // Clamping them to 1 snaps the originating pane back to the page edge when
  // its position is mirrored, losing several pixels during a drag or scroll.
  return { page: low + 1, offset: Math.max(0, (y - page.top) / page.height) };
}


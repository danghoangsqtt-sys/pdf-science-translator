export interface ReadingPosition {
  page: number;
  offset: number;
  x: number;
}
export const clampScale = (value: number): number =>
  Math.min(4, Math.max(0.4, Number(value.toFixed(2))));

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


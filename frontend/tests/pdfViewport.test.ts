import assert from 'node:assert/strict';
import test from 'node:test';
import { fitWidthScale, pageAtOffset } from '../src/components/pdfViewport.ts';

test('a portrait page fills the pane width', () => {
  assert.equal(fitWidthScale(644, [612, 612], 32), 1);
  assert.equal(fitWidthScale(950, [612], 32), 1.5);
});

test('the widest page decides, so a landscape page never overflows', () => {
  assert.equal(fitWidthScale(824, [612, 792], 32), 1);
});

test('the fitted scale rounds down so the page never ends wider than the pane', () => {
  // 0.99837… must not become 1.00 (612 px in a 611 px room).
  const scale = fitWidthScale(643, [612], 32);
  assert.equal(scale, 0.99);
  assert.ok(612 * scale <= 643 - 32);
});

test('a very narrow pane stops at the minimum zoom', () => {
  assert.equal(fitWidthScale(100, [612], 32), 0.4);
});

test('no pages or no room keeps 100%', () => {
  assert.equal(fitWidthScale(800, [], 32), 1);
  assert.equal(fitWidthScale(20, [612], 32), 1);
});

test('mirroring a position eight pixels into a page gutter keeps all eight pixels', () => {
  const pages = [{ top: 16, height: 100 }, { top: 132, height: 100 }];
  const y = 124;
  const position = pageAtOffset(pages, y);
  const page = pages[position.page - 1];

  assert.equal(page.top + page.height * position.offset, y);
});

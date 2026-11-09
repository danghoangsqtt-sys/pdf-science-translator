import assert from 'node:assert/strict';
import test from 'node:test';
import { pageAtOffset } from '../src/components/pdfViewport.ts';

test('mirroring a position eight pixels into a page gutter keeps all eight pixels', () => {
  const pages = [{ top: 16, height: 100 }, { top: 132, height: 100 }];
  const y = 124;
  const position = pageAtOffset(pages, y);
  const page = pages[position.page - 1];

  assert.equal(page.top + page.height * position.offset, y);
});

import assert from 'node:assert/strict';
import test from 'node:test';
import { displayFor, parseSavedWindow, planWindow } from '../electron/windowBounds.ts';

const screen = (width: number, height: number, x = 0) => ({ x, y: 0, width, height });
const inside = (outer: { x: number; y: number; width: number; height: number },
  inner: { x: number; y: number; width: number; height: number }) =>
  inner.x >= outer.x && inner.y >= outer.y
  && inner.x + inner.width <= outer.x + outer.width
  && inner.y + inner.height <= outer.y + outer.height;

for (const [width, height] of [[800, 560], [1024, 728], [1280, 984], [1366, 728], [1920, 1040]]) {
  test(`a ${width}x${height} work area gets a window that fits it`, () => {
    const area = screen(width, height);
    const plan = planWindow(area, null, [area]);
    assert.ok(inside(area, plan.bounds), JSON.stringify(plan));
    assert.ok(plan.minWidth <= width && plan.minHeight <= height);
    assert.ok(plan.bounds.width >= plan.minWidth && plan.bounds.height >= plan.minHeight);
  });
}

test('a projector-sized work area opens maximized, a wide monitor does not', () => {
  assert.equal(planWindow(screen(1024, 728), null, [screen(1024, 728)]).maximize, true);
  assert.equal(planWindow(screen(800, 560), null, [screen(800, 560)]).maximize, true);
  assert.equal(planWindow(screen(1920, 1040), null, [screen(1920, 1040)]).maximize, false);
});

test('a big screen keeps the preferred size, centred', () => {
  const plan = planWindow(screen(1920, 1040), null, [screen(1920, 1040)]);
  assert.deepEqual(plan.bounds, { x: 280, y: 80, width: 1360, height: 880 });
});

test('a window saved on an unplugged projector reopens on the current screen', () => {
  const laptop = screen(1366, 728);
  const saved = { bounds: { x: 1500, y: 20, width: 1000, height: 700 }, maximized: true };
  const plan = planWindow(laptop, saved, [laptop]);
  assert.ok(inside(laptop, plan.bounds));
  assert.equal(plan.maximize, false);
});

test('a saved window still on screen is reused and pulled fully inside', () => {
  const monitor = screen(1920, 1040);
  const saved = { bounds: { x: 1200, y: 400, width: 900, height: 700 }, maximized: false };
  const plan = planWindow(monitor, saved, [monitor]);
  assert.equal(plan.bounds.width, 900);
  assert.ok(inside(monitor, plan.bounds));
});

test('the screen holding most of a window is its home', () => {
  const left = screen(1366, 728);
  const right = screen(1024, 728, 1366);
  assert.equal(displayFor({ x: 1300, y: 10, width: 800, height: 600 }, [left, right]), right);
  assert.equal(displayFor({ x: 5000, y: 10, width: 800, height: 600 }, [left, right]), null);
});

test('a damaged saved state is ignored', () => {
  for (const value of [null, 'x', {}, { bounds: { x: 0, y: 0, width: 'a', height: 5 } },
    { bounds: { x: 0, y: 0, width: 20, height: 20 } }]) {
    assert.equal(parseSavedWindow(value), null);
  }
  assert.deepEqual(parseSavedWindow({ bounds: { x: 1, y: 2, width: 900, height: 600 }, maximized: true }),
    { bounds: { x: 1, y: 2, width: 900, height: 600 }, maximized: true });
});

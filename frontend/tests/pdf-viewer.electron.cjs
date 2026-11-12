// Run with: npm run test:viewer
// A hidden, real Chromium renderer with intercepted API responses. No engine,
// network service or user PDF is modified by these interaction regressions.
const { app, BrowserWindow } = require('electron');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
app.disableHardwareAcceleration();

const out = process.env.PDF_VIEWER_QA_DIR || path.join(os.tmpdir(), 'pdf-viewer-qa');
fs.mkdirSync(out, { recursive: true });
app.setPath('userData', path.join(out, 'profile'));
const checks = [];
// Print each check as it passes, so a stall shows where it happened.
const record = checks.push.bind(checks);
checks.push = (...items) => { for (const item of items) console.log('ok - ' + item); return record(...items); };
let win;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const js = (source) => win.webContents.executeJavaScript(source);
async function until(source, label) {
  for (let attempt = 0; attempt < 120; attempt++) {
    if (await js('Boolean(' + source + ')')) return;
    await delay(100);
  }
  throw new Error('Timed out: ' + label + '\n' + await js('document.body.innerText'));
}
function pdfBytes(count) {
  const objects = ['', '<< /Type /Catalog /Pages 2 0 R >>', '', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
  const kids = [];
  for (let number = 1; number <= count; number++) {
    const page = objects.length;
    const content = page + 1;
    kids.push(page + ' 0 R');
    const height = number % 2 ? 792 : 650;
    const text = 'BT /F1 22 Tf 50 ' + (height - 80) + ' Td (Review page ' + number + ') Tj ET';
    objects.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 ' + height + '] /Resources << /Font << /F1 3 0 R >> >> /Contents ' + content + ' 0 R >>');
    objects.push('<< /Length ' + Buffer.byteLength(text) + ' >>\nstream\n' + text + '\nendstream');
  }
  objects[2] = '<< /Type /Pages /Count ' + count + ' /Kids [' + kids.join(' ') + '] >>';
  let body = '%PDF-1.4\n';
  const offsets = [0];
  for (let index = 1; index < objects.length; index++) {
    offsets.push(Buffer.byteLength(body));
    body += index + ' 0 obj\n' + objects[index] + '\nendobj\n';
  }
  const start = Buffer.byteLength(body);
  body += 'xref\n0 ' + objects.length + '\n0000000000 65535 f \n';
  for (const offset of offsets.slice(1)) body += String(offset).padStart(10, '0') + ' 00000 n \n';
  body += 'trailer\n<< /Size ' + objects.length + ' /Root 1 0 R >>\nstartxref\n' + start + '\n%%EOF\n';
  return Buffer.from(body);
}
let resultPdf = pdfBytes(9);
let resourcesReady = false;
// Job status requests to drop before answering (backend busy or restarting),
// and whether the job has vanished (backend restarted: 404).
let statusFailures = 0;
let statusNotFound = false;
// While set, every status request reports a job still running at page 3/9.
let statusRunning = false;
// The multipart body of the latest job request, to see what the app sent.
let lastJobBody = '';
async function selectFile(bytes, name) {
  await js('(() => { const bytes = Uint8Array.from(atob(' + JSON.stringify(bytes.toString('base64')) + '), c => c.charCodeAt(0)); const data = new DataTransfer(); data.items.add(new File([bytes], ' + JSON.stringify(name) + ', {type:"application/pdf"})); const input = document.querySelector("input[type=file]"); input.files=data.files; input.dispatchEvent(new Event("change",{bubbles:true})); })()');
}
async function metrics() {
  return js('Array.from(document.querySelectorAll("[data-pdf-viewport]"), e => ({top:e.scrollTop,left:e.scrollLeft,height:e.clientHeight,total:e.scrollHeight,width:e.clientWidth,scrollWidth:e.scrollWidth,pages:e.querySelectorAll("[data-page-number]").length,canvases:e.querySelectorAll("canvas").length,rect:(()=>{const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}})()}))');
}
async function wheel(side, deltaY, ctrl = false) {
  const views = await metrics();
  const rect = views[side].rect;
  const x = Math.round(rect.x + rect.width / 2);
  const y = Math.round(rect.y + Math.min(180, rect.height / 2));
  win.webContents.focus();
  await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  if (ctrl) {
    await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', {
      type: 'mouseWheel', x, y, deltaX: 0, deltaY, modifiers: 2,
    });
  } else {
    await win.webContents.debugger.sendCommand('Input.synthesizeScrollGesture', {
      x, y, yDistance: -deltaY, speed: 5000, gestureSourceType: 'mouse',
    });
  }
  await delay(250);
}
async function aligned(label) {
  const [left, right] = await metrics();
  assert.ok(Math.abs(left.top - right.top) <= 2, label + ': vertical sync ' + left.top + '/' + right.top);
  assert.ok(Math.abs(left.left - right.left) <= 2, label + ': horizontal sync');
  checks.push(label);
}
// Real wheel events: unlike a synthesized gesture, they do not wait for the
// scroll to finish, so a pane that moves while the toolbar hides cannot stall them.
async function scrollWith(side, deltaY) {
  const rect = (await metrics())[side].rect;
  const x = Math.round(rect.x + rect.width / 2);
  const y = Math.round(rect.y + Math.min(180, rect.height / 2));
  await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  for (let step = 0; step < 4; step++) {
    await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', {
      type: 'mouseWheel', x, y, deltaX: 0, deltaY: deltaY / 4, modifiers: 0 });
    await delay(60);
  }
  await delay(450);
}
// The ▲/▼ toggle, clicked with real mouse events; only when not already so.
async function setCollapsed(on) {
  const rect = await js('(() => { const b = document.querySelector("[data-chrome-toggle]"); if (!b || b.getAttribute("aria-expanded") !== '
    + JSON.stringify(on ? 'true' : 'false') + ') return null; const r = b.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; })()');
  if (!rect) return;
  const at = { x: Math.round(rect.x), y: Math.round(rect.y), button: 'left', clickCount: 1 };
  await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mouseMoved', x: at.x, y: at.y });
  await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mousePressed', ...at });
  await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mouseReleased', ...at });
  // The hidden test window only paints on input, so keep the pointer moving
  // until the 200 ms transition has finished.
  for (let step = 0; step < 8; step++) {
    await delay(50);
    await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mouseMoved', x: at.x + (step % 2), y: at.y });
  }
  await delay(100);
}
const toggleState = () => js('(() => { const b = document.querySelector("[data-chrome-toggle]"); return b && { expanded: b.getAttribute("aria-expanded"), label: b.getAttribute("aria-label"), visible: (() => { const r = b.getBoundingClientRect(); return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; })() }; })()');
async function pointerAt(x, y) {
  await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  await delay(350);
}
const chromeHidden = () => js('document.querySelector("[data-chrome]").dataset.hidden === "true"');
const inViewport = (text) => js('(() => { const b = Array.from(document.querySelectorAll("button")).find(e => e.textContent.includes('
  + JSON.stringify(text) + ')); if (!b) return false; const r = b.getBoundingClientRect(); return r.height > 0 && r.top >= 0 && r.bottom <= innerHeight; })()');
async function clickText(text) {
  await js('Array.from(document.querySelectorAll("button")).find(e => e.textContent.includes(' + JSON.stringify(text) + ')).click()');
  await delay(200);
}

// A renderer that stops answering must fail the run, not hang it.
setTimeout(async () => {
  console.error('Watchdog: viewer regression did not finish in 4 minutes after: ' + (checks.at(-1) || 'start'));
  try { if (win && !win.isDestroyed()) fs.writeFileSync(path.join(out, 'viewer-stall.png'), (await win.webContents.capturePage()).toPNG()); } catch { /* best effort */ }
  app.exit(1);
}, 240000).unref();
app.whenReady().then(async () => {
  win = new BrowserWindow({ show: false, width: 1360, height: 960,
    webPreferences: { sandbox: true, contextIsolation: true, nodeIntegration: false, backgroundThrottling: false,
      preload: path.join(__dirname, '../dist-electron/preload.mjs'),
      additionalArguments: ['--pdftranslate-api-token=viewer-test', '--pdftranslate-api-base=http://127.0.0.1:38089/api'],
    } });
  const errors = [];
  win.webContents.on('console-message', ({ level, message }) => {
    if (['warning', 'error'].includes(level) && !message.includes('Content Security Policy') && !message.includes('React DevTools')) errors.push(message);
  });
  win.webContents.debugger.attach('1.3');
  await win.webContents.debugger.sendCommand('Fetch.enable', { patterns: [{ urlPattern: 'http://127.0.0.1:38089/*' }] });
  win.webContents.debugger.on('message', async (_event, method, event) => {
    if (method !== 'Fetch.requestPaused') return;
    const url = new URL(event.request.url);
    let body;
    let contentType = 'application/json';
    let responseCode = 200;
    const isStatus = event.request.method === 'GET' && /\/jobs\/[^/]+$/.test(url.pathname);
    if (isStatus && statusFailures > 0) {
      statusFailures -= 1;
      await win.webContents.debugger.sendCommand('Fetch.failRequest', {
        requestId: event.requestId, errorReason: 'ConnectionRefused',
      });
      return;
    }
    if (isStatus && statusNotFound) responseCode = 404;
    if (event.request.method === 'POST' && url.pathname.endsWith('/jobs')) lastJobBody = event.request.postData || '';
    if (event.request.method === 'OPTIONS') body = Buffer.from('');
    else if (url.pathname.endsWith('/health')) body = Buffer.from(JSON.stringify({ status: 'ready' }));
    else if (url.pathname.endsWith('/capabilities')) body = Buffer.from(JSON.stringify({
      offline: true, default_profile: 'balanced',
      profiles: [
        {id:'fast',label:'Nhanh',description:'Ưu tiên tốc độ.',available:true,message:'Sẵn sàng'},
        {id:'balanced',label:'Cân bằng',description:'Cân bằng thời gian.',available:true,message:'Sẵn sàng'},
        {id:'quality',label:'Chất lượng cao',description:'Xử lý kỹ hơn.',available:true,message:'Sẵn sàng'},
      ].map(profile => ({ ...profile, available: resourcesReady,
        reason_code: resourcesReady ? null : 'LOCAL_PREPARING',
        message: resourcesReady ? 'Sẵn sàng' : 'Đang chuẩn bị dữ liệu cục bộ.' })),
    }));
    else if (url.pathname.endsWith('/result')) { body = resultPdf; contentType = 'application/pdf'; }
    else if (url.pathname.endsWith('/jobs')) body = Buffer.from(JSON.stringify({ job_id: 'viewer-test' }));
    else if (responseCode === 404) body = Buffer.from(JSON.stringify({ detail: 'Không tìm thấy tác vụ.' }));
    else if (statusRunning) body = Buffer.from(JSON.stringify({ status: 'running', progress: { done: 3, total: 9 } }));
    else body = Buffer.from(JSON.stringify({ status: 'complete', progress: { done: 9, total: 9 } }));
    await win.webContents.debugger.sendCommand('Fetch.fulfillRequest', {
      requestId: event.requestId, responseCode, responseHeaders: [
        { name: 'Content-Type', value: contentType }, { name: 'Access-Control-Allow-Origin', value: '*' },
        { name: 'Access-Control-Allow-Headers', value: '*' }, { name: 'Access-Control-Allow-Methods', value: '*' },
      ], body: body.toString('base64'),
    });
  });
  await win.loadFile(path.join(__dirname, '../dist/index.html'));
  await win.webContents.debugger.sendCommand('Emulation.setFocusEmulationEnabled', { enabled: true });
  await until('document.querySelector("input[type=file]")', 'app ready');
  // A mode picked in an earlier run must not change this run's layout.
  await js('localStorage.clear()');
  assert.equal(await js('window.pdftranslate?.apiBaseUrl'), 'http://127.0.0.1:38089/api');
  assert.equal(await js('window.pdftranslate?.apiToken'), 'viewer-test');
  checks.push('Production sandbox preload supplies the private API port and session token');
  await until('Array.from(document.images).every(image => image.complete && image.naturalWidth > 0)', 'packaged image assets');
  checks.push('Packaged image assets load through file URLs');
  await until('document.querySelector("#processing-profile")', 'processing profiles');
  await until('document.body.innerText.includes("LOCAL_PREPARING")', 'preparing local resources');
  assert.ok(!await js('document.querySelector("header").innerText.includes("Bộ xử lý sẵn sàng")'));
  assert.equal(await js('Array.from(document.querySelectorAll("button")).find(b=>b.textContent.includes("Dịch ngay")).disabled'), true);
  resourcesReady = true;
  await js('document.querySelector("button[title=\\"Kiểm tra dữ liệu cục bộ\\"]").click()');
  await until('document.querySelector("header").innerText.includes("Bộ xử lý sẵn sàng")', 'local resources ready');
  checks.push('Preparing resources blocks translation and does not report false readiness');
  assert.deepEqual(await js('Array.from(document.querySelector("#processing-profile").options, o=>o.value)'), ['fast','balanced','quality']);
  assert.equal(await js('document.querySelector("#engine")'), null);
  assert.equal(await js('document.querySelector("#ollama-model")'), null);
  assert.ok(!/ollama|translategemma|qwen|azure|google/i.test(await js('document.body.innerText')));
  checks.push('Public UI only exposes three processing profiles');
  // The older interaction cases measure panes that must not move under them.
  await setCollapsed(false);
  await selectFile(pdfBytes(9), 'viewer-nine-pages.pdf');
  await until('document.querySelectorAll("[data-page-number]:not(.react-pdf__Page)").length === 9', 'source pages');
  await until('document.querySelector("canvas")?.width > 0', 'first page rendered');
  await delay(150);
  await wheel(0, 1100);
  let views = await metrics();
  assert.ok(views[0].top > 900, 'wheel scrolls across pages: ' + JSON.stringify(views));
  const beforeResult = views[0].top;
  checks.push('Continuous wheel scrolling across pages');
  await until('Array.from(document.querySelectorAll("button")).some(e=>e.textContent.includes("Dịch ngay")&&!e.disabled)', 'translate available');
  statusFailures = 2;
  await clickText('Dịch ngay');
  await until('document.querySelectorAll("[data-pdf-viewport]").length === 2 && document.querySelectorAll("[data-page-number]:not(.react-pdf__Page)").length === 18', 'result pages');
  assert.equal(statusFailures, 0, 'both dropped status requests were retried');
  assert.ok(!await js('document.body.innerText.includes("Không thể kiểm tra tiến độ")'));
  checks.push('Transient status failures are retried instead of abandoning the job');
  await delay(300);
  await aligned('Late result follows the source reading position');
  assert.ok(Math.abs((await metrics())[0].top - beforeResult) <= 2);
  assert.ok((await metrics()).every(e => e.canvases < 9), 'only nearby canvases rendered');
  checks.push('Offscreen pages do not allocate canvases');

  await wheel(1, 600);
  await aligned('Right-to-left wheel synchronization');
  await wheel(0, -350);
  await aligned('Immediate reverse direction synchronization');
  const oldZoom = await js('Array.from(document.querySelectorAll("[aria-label=\\"Mức thu phóng\\"]"),e=>e.textContent)');
  await wheel(0, -180, true);
  const zooms = await js('Array.from(document.querySelectorAll("[aria-label=\\"Mức thu phóng\\"]"),e=>e.textContent)');
  assert.notEqual(zooms[0], oldZoom[0]);
  assert.equal(zooms[0], zooms[1]);
  assert.equal(win.webContents.getZoomFactor(), 1, 'whole app must not zoom');
  await aligned('Ctrl+wheel zooms both PDFs without zooming the app');

  views = await metrics();
  const rect = views[0].rect;
  const x = Math.round(rect.x + rect.width / 2);
  const y = Math.round(rect.y + 180);
  const beforeDrag = views[0].top;
  for (const input of [
    { type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1 },
    { type: 'mouseMoved', x: x - 60, y: y - 100, button: 'left', buttons: 1 },
    { type: 'mouseReleased', x: x - 60, y: y - 100, button: 'left', buttons: 0, clickCount: 1 },
  ]) {
    await win.webContents.debugger.sendCommand('Input.dispatchMouseEvent', input);
    await delay(50);
  }
  await delay(250);
  assert.ok(Math.abs((await metrics())[0].top - beforeDrag - 100) <= 2,
    'drag pans vertically: ' + beforeDrag + ' -> ' + (await metrics())[0].top);
  await aligned('Left-button drag pans and synchronizes both axes');

  await clickText('Đồng bộ 2 khung');
  const leftBefore = (await metrics())[0].top;
  await wheel(1, 450);
  assert.ok(Math.abs((await metrics())[0].top - leftBefore) <= 1, 'unsynced left must stay');
  await wheel(1, 120, true);
  const separateZooms = await js('Array.from(document.querySelectorAll("[aria-label=\\"Mức thu phóng\\"]"),e=>e.textContent)');
  assert.notEqual(separateZooms[0], separateZooms[1]);
  checks.push('Sync off allows independent scroll and zoom');
  await clickText('Đồng bộ 2 khung');
  await delay(300);
  await aligned('Re-enabling sync follows the last active pane');
  await js('document.querySelectorAll("button[title=\\"Trang sau\\"]")[1].click()');
  await delay(250);
  await aligned('Page navigation remains synchronized');
  const stable = (await metrics())[0].top;
  await delay(500);
  assert.equal((await metrics())[0].top, stable, 'no scroll feedback loop');
  checks.push('Mirrored scrolling settles without feedback');

  fs.writeFileSync(path.join(out, 'viewer-paired.png'), (await win.webContents.capturePage()).toPNG());

  // ENH-004: projector 4:3, 5:4 and wide screens.
  const pageShown = (index) => js('(() => { const v = document.querySelectorAll("[data-pdf-viewport]")[' + index
    + ']; const m = v && v.closest("section").innerText.match(/Trang (\\d+)/); return m ? Number(m[1]) : 0; })()');
  for (const [width, height] of [[800, 600], [1024, 768], [1280, 1024], [1366, 768], [1920, 1080]]) {
    win.setContentSize(width, height);
    await delay(500);
    await pointerAt(40, 2);
    const layout = await js(`(() => {
      const inView = (e) => { if (!e) return false; const r = e.getBoundingClientRect();
        return r.width > 0 && r.left >= 0 && r.top >= 0 && r.right <= innerWidth + 0.5 && r.bottom <= innerHeight + 0.5; };
      const button = (text) => Array.from(document.querySelectorAll("button")).find(b => b.textContent.includes(text));
      const panes = Array.from(document.querySelectorAll("[data-pdf-viewport]"));
      return { innerWidth, innerHeight, scrollWidth: document.documentElement.scrollWidth,
        bodyScroll: document.body.scrollWidth, translate: inView(button("Dịch ngay")),
        download: inView(button("Tải")), panes: panes.length,
        paneHeight: Math.max(0, ...panes.map(p => p.closest("section").getBoundingClientRect().height)),
        mode: document.querySelector("[data-view-mode][aria-pressed=true]")?.dataset.viewMode };
    })()`);
    const label = width + 'x' + height;
    assert.equal(layout.innerWidth, width, label + ' content size');
    assert.ok(layout.scrollWidth <= width && layout.bodyScroll <= width, label + ' no horizontal page scroll: ' + JSON.stringify(layout));
    assert.ok(layout.translate, label + ' translate button visible: ' + JSON.stringify(layout));
    assert.ok(layout.download, label + ' download button visible: ' + JSON.stringify(layout));
    assert.ok(layout.paneHeight >= height * 0.55, label + ' PDF keeps most of the height: ' + JSON.stringify(layout));
    if (width < 1200) {
      assert.equal(layout.panes, 1, label + ' one pane on a narrow screen');
      assert.equal(layout.mode, 'translated', label + ' a fresh result is shown first');
    } else {
      assert.equal(layout.panes, 2, label + ' side by side when wide enough');
    }
    fs.writeFileSync(path.join(out, 'viewer-' + label + '.png'), (await win.webContents.capturePage()).toPNG());
    checks.push('Usable layout at ' + label);
  }
  win.setContentSize(1024, 768);
  await delay(400);
  await wheel(0, 1500);
  const readingPage = await pageShown(0);
  assert.ok(readingPage > 1, 'scrolled into the document');
  await clickText('Bản gốc');
  await delay(600);
  assert.equal(await js('document.querySelectorAll("[data-pdf-viewport]").length'), 1);
  assert.equal(await pageShown(0), readingPage, 'switching panes keeps the reading page');
  await clickText('Song song');
  await delay(600);
  assert.equal(await js('document.querySelectorAll("[data-pdf-viewport]").length'), 2, 'side by side on request');
  await aligned('Single-pane switching keeps the reading position and Song song can be forced');
  // ENH-005: reading space, collapsed by hand with the ▲/▼ toggle.
  await delay(200);
  await js('Array.from(document.querySelectorAll("[data-fit-width]")).filter(b => !b.disabled).forEach(b => b.click())');
  await delay(400);
  for (const [width, height] of [[800, 600], [1024, 768], [1366, 768]]) {
    const label = width + 'x' + height;
    win.setContentSize(width, height);
    await delay(500);
    await setCollapsed(false);
    assert.equal(await chromeHidden(), false, label + ' toolbar shown before reading');
    assert.deepEqual(await toggleState(), { expanded: 'true', label: 'Thu gọn thanh công cụ', visible: true });
    await scrollWith(0, 700);
    assert.equal(await chromeHidden(), false, label + ' scrolling alone does not hide the toolbar');
    await setCollapsed(true);
    assert.equal(await chromeHidden(), true, label + ' ▲ collapses the toolbar');
    assert.deepEqual(await toggleState(), { expanded: 'false', label: 'Mở rộng thanh công cụ', visible: true },
      label + ' the toggle stays reachable while collapsed');
    const reading = await js(`(() => { const panes = Array.from(document.querySelectorAll("[data-pdf-viewport]"));
      return {
        height: Math.max(...panes.map(p => p.closest("section").getBoundingClientRect().height)),
        overflow: Math.max(...panes.map(p => p.scrollWidth - p.clientWidth)),
        zoom: document.querySelector("[aria-label=\\"Mức thu phóng\\"]").textContent }; })()`);
    assert.ok(reading.height >= height * 0.85, label + ' PDF fills the window while reading: ' + JSON.stringify(reading));
    assert.ok(reading.overflow <= 1, label + ' fitted page does not overflow sideways: ' + JSON.stringify(reading));
    assert.equal(reading.zoom, 'Vừa khung');
    fs.writeFileSync(path.join(out, 'viewer-reading-' + label + '.png'), (await win.webContents.capturePage()).toPNG());
    await scrollWith(0, -300);
    await pointerAt(60, 3);
    assert.equal(await chromeHidden(), true, label + ' scrolling up or the top edge does not reopen it');
    await setCollapsed(false);
    assert.equal(await chromeHidden(), false, label + ' ▼ expands the toolbar');
    assert.ok(await inViewport('Dịch ngay'), label + ' translate button back on screen');
    checks.push('Reading space at ' + label + ': ▲/▼ collapses and expands, scrolling does not, PDF fits width and fills the height');
  }

  const zoomLabel = () => js('document.querySelector("[aria-label=\\"Mức thu phóng\\"]").textContent');
  await js('document.querySelector("button[title^=\\"Phóng to\\"]").click()');
  await delay(300);
  const custom = await zoomLabel();
  assert.match(custom, /%$/, 'manual zoom leaves fit mode');
  win.setContentSize(900, 700);
  await delay(500);
  assert.equal(await zoomLabel(), custom, 'a manual zoom survives a window resize');
  await js('document.querySelector("[data-fit-width]").click()');
  await delay(400);
  assert.equal(await zoomLabel(), 'Vừa khung');
  checks.push('Manual zoom is kept across resizes until Vừa khung is chosen again');

  statusRunning = true;
  await pointerAt(40, 2);
  await clickText('Dịch ngay');
  await until('document.body.innerText.includes("Đã dịch 3 / 9")', 'job running');
  // Earlier cases may have left the pane at the end of the document.
  await js('document.querySelectorAll("[data-pdf-viewport]").forEach(v => { v.scrollTop = 0; })');
  await delay(500);
  await setCollapsed(true);
  assert.equal(await chromeHidden(), true);
  assert.ok(await js('Boolean(document.querySelector("[data-reading-progress]"))'), 'thin progress line while hidden');
  assert.equal(await js('document.querySelector("[data-reading-progress]").getAttribute("aria-valuenow")'), '33');
  statusRunning = false;
  await until('!document.body.innerText.includes("Đang dịch...")', 'job finished');
  await delay(300);
  assert.equal(await chromeHidden(), false, 'the job ending brings the toolbar back');
  checks.push('A hidden toolbar keeps a progress line and returns when the job ends');

  win.setContentSize(1360, 960);
  await delay(400);

  await setCollapsed(true);
  assert.equal(await chromeHidden(), true);
  statusNotFound = true;
  await clickText('Dịch ngay');
  await until('document.body.innerText.includes("khởi động lại")', 'restarted backend reported');
  await until('Array.from(document.querySelectorAll("button")).some(e=>e.textContent.includes("Dịch ngay")&&!e.disabled)', 'translate available again');
  statusNotFound = false;
  assert.equal(await chromeHidden(), false, 'an error brings the toolbar back');
  checks.push('A job lost to a backend restart is reported and translation can start again');

  // ENH-006: source language.
  const choose = (id, value) => js('(() => { const s = document.getElementById(' + JSON.stringify(id) + '); s.value = '
    + JSON.stringify(value) + '; s.dispatchEvent(new Event("change", { bubbles: true })); })()');
  const languages = () => js('[document.getElementById("source-lang").value, document.getElementById("target-lang").value]');
  await pointerAt(40, 2);
  assert.deepEqual(await languages(), ['auto', 'vi'], 'auto-detect by default');
  assert.equal(await js('document.querySelector("[aria-label=\\"Đảo chiều ngôn ngữ\\"]").disabled'), true);
  await choose('source-lang', 'vi');
  await delay(150);
  assert.deepEqual(await languages(), ['vi', 'en'], 'choosing the target language as source flips the target');
  await js('document.querySelector("[aria-label=\\"Đảo chiều ngôn ngữ\\"]").click()');
  await delay(150);
  assert.deepEqual(await languages(), ['en', 'vi'], 'swap reverses the direction');
  await choose('target-lang', 'en');
  await delay(150);
  assert.deepEqual(await languages(), ['auto', 'en'], 'a target equal to the source resets the source to auto');
  await choose('source-lang', 'fr');
  await choose('target-lang', 'vi');
  await delay(150);
  await clickText('Dịch ngay');
  await until('Array.from(document.querySelectorAll("button")).some(e=>e.textContent.includes("Dịch ngay")&&!e.disabled)', 'job done');
  const CRLF = String.fromCharCode(13, 10);
  const field = (name, value) => lastJobBody.includes('name="' + name + '"' + CRLF + CRLF + value + CRLF);
  assert.ok(field('source_language', 'fr'), 'the chosen source is sent: ' + lastJobBody.slice(0, 300));
  assert.ok(field('target_language', 'vi'));
  await choose('source-lang', 'auto');
  checks.push('Source language: auto by default, swap, conflict handling, sent with the job');
  await selectFile(pdfBytes(200), 'viewer-book.pdf');
  await until('document.querySelectorAll("[data-page-number]:not(.react-pdf__Page)").length === 200', 'large document');
  await delay(300);
  const book = (await metrics())[0];
  assert.equal(book.top, 0);
  assert.ok(book.canvases < 6, 'large document must not render all pages');
  assert.equal(await js('document.querySelector("[aria-label=\\"Mức thu phóng\\"]").textContent'), 'Vừa khung');
  checks.push('New 200-page document resets view and renders only nearby pages');
  // Last, because a reload resets the app: the collapsed choice survives it.
  await setCollapsed(true);
  assert.equal(await js('localStorage.getItem("pdftranslate.toolbarCollapsed")'), '1');
  js('location.reload()').catch(() => {});
  await delay(1500);
  await until('document.querySelector("#processing-profile")', 'reloaded');
  assert.equal(await js('document.querySelector("[data-chrome-toggle]")'), null, 'no toggle before a document is open');
  await selectFile(pdfBytes(9), 'viewer-nine-pages.pdf');
  await until('document.querySelectorAll("[data-page-number]:not(.react-pdf__Page)").length === 9', 'source pages after reload');
  await delay(400);
  assert.equal(await chromeHidden(), true, 'the collapsed choice is remembered');
  await setCollapsed(false);
  assert.equal(await js('localStorage.getItem("pdftranslate.toolbarCollapsed")'), '0');
  checks.push('The collapsed toolbar is remembered across a reload');
  assert.deepEqual(errors, [], 'renderer errors');
  fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify({ passed: checks, rendererErrors: errors }, null, 2));
  console.log(JSON.stringify({ passed: checks.length, out }));
  app.exit(0);
}).catch(async (error) => {
  if (win && !win.isDestroyed()) {
    try {
      fs.writeFileSync(path.join(out, 'viewer-failure.png'), (await win.webContents.capturePage()).toPNG());
    } catch { /* A failed screenshot must not keep a failed test process alive. */ }
  }
  fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify({ passed: checks, error: error.stack }, null, 2));
  console.error(error);
  app.exit(1);
});


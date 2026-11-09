import { app, BrowserWindow, dialog, ipcMain, session } from 'electron';
import path from 'node:path';
import { spawn, spawnSync, ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import net from 'node:net';

// Diagnostic-only file log: console output from a windowed (non-console)
// Electron build is not reliably captured by a parent shell even when its
// stdout/stderr are redirected, which made an earlier silent-exit crash
// impossible to diagnose from outside the process. Written before anything
// else so it survives a failure during module load itself, not only inside
// app.whenReady().
const CRASH_LOG_PATH = path.join(os.tmpdir(), 'pdftranslate-local.log');
function fileLog(...args: unknown[]) {
  try {
    const line = `[${new Date().toISOString()}] ${args.map((a) => (a instanceof Error ? `${a.name}: ${a.message}\n${a.stack}` : String(a))).join(' ')}\n`;
    fs.appendFileSync(CRASH_LOG_PATH, line);
  } catch {
    // logging must never be the thing that crashes the app
  }
}
fileLog('Local application loading');

const API_TOKEN = randomBytes(32).toString('base64url');
let apiPort = 8089;
process.env.PDFTRANSLATE_API_TOKEN = API_TOKEN;

// Global EPIPE Guard
process.on('uncaughtException', (err) => {
  fileLog('Local application failure');
  if ((err as NodeJS.ErrnoException).code === 'EPIPE') {
    return;
  }
  try {
    dialog.showErrorBox(
      'PDF Translate - Unexpected Error',
      'Ứng dụng gặp sự cố. Hãy khởi động lại. Mã hỗ trợ: LOCAL_APP_FAILED.'
    );
  } catch {
    // dialog might not be ready yet
  }
});

process.on('unhandledRejection', () => {
  fileLog('Local application operation failed');
});

process.stdout?.on('error', () => {});
process.stderr?.on('error', () => {});

function getProjectRoot(): string {
  if (app.isPackaged) {
    return process.resourcesPath;
  } else {
    // Dev mode: __dirname = frontend/dist-electron/
    // Go up 2 levels: dist-electron -> frontend -> vp-pdf root
    return path.resolve(__dirname, '..', '..');
  }
}

const PROJECT_ROOT = getProjectRoot();

process.env.APP_ROOT = path.join(__dirname, '..');

export const VITE_DEV_SERVER_URL = process.env['VITE_DEV_SERVER_URL'];
export const MAIN_DIST = path.join(process.env.APP_ROOT, 'dist-electron');
export const RENDERER_DIST = path.join(process.env.APP_ROOT, 'dist');

process.env.VITE_PUBLIC = VITE_DEV_SERVER_URL
  ? path.join(process.env.APP_ROOT, 'public')
  : RENDERER_DIST;

let win: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

let intentionalShutdown = false;
let restartAttempts = 0;
const MAX_RESTART_ATTEMPTS = 5;
let restartResetTimer: NodeJS.Timeout | null = null;

function safeLog(...args: unknown[]) {
  try {
    console.log(...args);
  } catch {
    // ignore
  }
  fileLog(...args);
}

function startPythonBackend() {
  const pythonCandidates = app.isPackaged
    ? [path.join(PROJECT_ROOT, 'python_runtime', 'python.exe')]
    : [
        path.join(PROJECT_ROOT, 'BAN-CHAY', '.venv312', 'Scripts', 'python.exe'),
        path.join(PROJECT_ROOT, 'BAN-CHAY', 'python_runtime', 'python.exe'),
        path.join(PROJECT_ROOT, '.venv312', 'Scripts', 'python.exe'),
        path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'),
      ];
  const pythonExe = pythonCandidates.find((candidate) => fs.existsSync(candidate));
  const runServerScript = path.join(PROJECT_ROOT, 'backend', 'server', 'run_server.py');
  const userDataPath = path.join(app.getPath('userData'), 'data');

  safeLog('========== PDF Translate Backend ==========');
  safeLog(`  Project Root : ${PROJECT_ROOT}`);
  safeLog(`  Python Exe   : ${pythonExe ?? '(not found)'}`);
  safeLog(`  Script       : ${runServerScript}`);
  safeLog(`  Data Dir     : ${userDataPath}`);
  safeLog(`  Packaged     : ${app.isPackaged}`);

  if (!pythonExe) {
    safeLog(`[FATAL] Python executable not found. Checked: ${pythonCandidates.join(', ')}`);
    dialog.showErrorBox(
      'PDF Translate - Backend Not Found',
      'Thiếu thành phần xử lý cục bộ. Hãy cài lại ứng dụng. Mã hỗ trợ: LOCAL_COMPONENT_MISSING.'
    );
    return;
  }

  if (!fs.existsSync(runServerScript)) {
    safeLog(`[FATAL] Server script not found: ${runServerScript}`);
    dialog.showErrorBox(
      'PDF Translate - Server Script Not Found',
      'Thiếu thành phần ứng dụng. Hãy cài lại bản được cấp. Mã hỗ trợ: LOCAL_COMPONENT_MISSING.'
    );
    return;
  }

  const backendEnvironment: NodeJS.ProcessEnv = {
    ...process.env,
    PDFTRANSLATE_API_TOKEN: API_TOKEN,
    PDFTRANSLATE_DATA_DIR: userDataPath,
    PDFTRANSLATE_API_PORT: String(apiPort),
    PDF_TRANSLATE_OFFLINE: '1',
    PDF_TRANSLATE_OFFLINE_PACK: process.env.PDF_TRANSLATE_OFFLINE_PACK || path.join(PROJECT_ROOT, 'offline-data'),
  };

  pythonProcess = spawn(pythonExe, ['-s', runServerScript], {
    cwd: path.join(PROJECT_ROOT, 'backend'),
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: backendEnvironment,
    windowsHide: true,
  });

  pythonProcess.stdout?.on('data', (data) => {
    if (data.length) safeLog('Local backend activity');
  });

  pythonProcess.stderr?.on('data', (data) => {
    if (data.length) safeLog('Local backend diagnostic event');
  });

  pythonProcess.stdout?.on('error', () => {});
  pythonProcess.stderr?.on('error', () => {});

  pythonProcess.on('error', (err) => {
    safeLog('Local backend could not start');
    dialog.showErrorBox(
      'PDF Translate - Lỗi khởi động Backend',
      'Không thể khởi động bộ xử lý cục bộ. Mã hỗ trợ: LOCAL_START_FAILED.'
    );
  });

  pythonProcess.on('spawn', () => {
    if (restartResetTimer) clearTimeout(restartResetTimer);
    restartResetTimer = setTimeout(() => {
      restartAttempts = 0;
      safeLog('[Backend] Stable for 30s - restart budget reset.');
    }, 30000);
  });

  pythonProcess.on('close', (code) => {
    safeLog(`[Backend] process exited with code ${code}`);
    pythonProcess = null;

    if (intentionalShutdown) {
      return;
    }

    if (restartResetTimer) {
      clearTimeout(restartResetTimer);
      restartResetTimer = null;
    }

    if (restartAttempts >= MAX_RESTART_ATTEMPTS) {
      safeLog(`[Backend] Giving up after ${restartAttempts} restart attempts.`);
      dialog.showErrorBox(
        'PDF Translate - Backend gặp sự cố liên tục',
        `Máy chủ xử lý đã dừng đột ngột ${restartAttempts} lần liên tiếp và sẽ không tự khởi động lại nữa.\n\nVui lòng khởi động lại ứng dụng.`
      );
      return;
    }

    restartAttempts += 1;
    const delayMs = Math.min(1000 * 2 ** (restartAttempts - 1), 30000);
    safeLog(`[Backend] Unexpected exit - restarting in ${delayMs}ms (attempt ${restartAttempts}/${MAX_RESTART_ATTEMPTS})`);
    setTimeout(() => {
      if (!intentionalShutdown) {
        startPythonBackend();
      }
    }, delayMs);
  });
}

function createWindow() {
  const preloadPath = path.join(__dirname, 'preload.mjs');
  fileLog('createWindow start, preload =', preloadPath, 'exists =', fs.existsSync(preloadPath));
  const windowIconPath = path.join(process.env.VITE_PUBLIC as string, 'icon.png');
  win = new BrowserWindow({
    width: 1360,
    height: 880,
    title: 'PDF Translate',
    icon: windowIconPath,
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      devTools: !app.isPackaged,
      additionalArguments: [`--pdftranslate-api-token=${API_TOKEN}`,
        `--pdftranslate-api-base=http://127.0.0.1:${apiPort}/api`],
    },
  });
  fileLog('BrowserWindow constructed');
  win.removeMenu();
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  win.on('closed', () => fileLog('window closed event'));
  win.webContents.on('render-process-gone', (_event, details) => {
    fileLog('render-process-gone', JSON.stringify(details));
  });
  win.webContents.on('did-fail-load', () => {
    safeLog('Local interface could not load');
  });
  win.webContents.on('did-finish-load', () => fileLog('did-finish-load'));

  const target = VITE_DEV_SERVER_URL ?? path.join(RENDERER_DIST, 'index.html');
  fileLog('loading renderer from', target, 'RENDERER_DIST exists =', fs.existsSync(RENDERER_DIST));
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL).catch(() => fileLog('Local interface unavailable'));
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'index.html')).catch(() => fileLog('Local interface unavailable'));
  }
  fileLog('createWindow end (load call issued)');
}

ipcMain.handle('open-external', async () => false);

app.on('window-all-closed', () => {
  fileLog('window-all-closed fired');
  intentionalShutdown = true;
  if (pythonProcess) {
    safeLog('Killing python backend process...');
    try {
      if (process.platform === 'win32' && pythonProcess.pid) {
        // Wait for the whole tree (backend + local worker) to stop before quitting;
        // a fire-and-forget taskkill could lose the race with app.quit().
        spawnSync('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t'], { windowsHide: true, timeout: 15000 });
      } else {
        pythonProcess.kill('SIGTERM');
      }
    } catch (e) {
      safeLog('Local backend shutdown failed');
    }
  }
  if (process.platform !== 'darwin') {
    app.quit();
    win = null;
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

app.whenReady().then(async () => {
  apiPort = await new Promise<number>((resolve, reject) => {
    const probe = net.createServer();
    probe.once('error', reject);
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address() as net.AddressInfo;
      probe.close(() => resolve(address.port));
    });
  });
  session.defaultSession.webRequest.onBeforeRequest((details, callback) => {
    try {
      const url = new URL(details.url);
      const localAsset = ['file:', 'data:', 'blob:'].includes(url.protocol);
      const localApi = url.protocol === 'http:' && url.hostname === '127.0.0.1' && Number(url.port) === apiPort;
      const localDev = !app.isPackaged && ['http:', 'ws:'].includes(url.protocol)
        && ['127.0.0.1', 'localhost'].includes(url.hostname) && Number(url.port) === 5173;
      callback({ cancel: !(localAsset || localApi || localDev) });
    } catch { callback({ cancel: true }); }
  });
  fileLog('app ready, isPackaged =', app.isPackaged, 'resourcesPath =', process.resourcesPath);
  startPythonBackend();
  createWindow();
}).catch(() => {
  fileLog('Local application startup failed');
});

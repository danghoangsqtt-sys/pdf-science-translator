import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import path from 'node:path';
import { spawn, ChildProcess } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';

// Diagnostic-only file log: console output from a windowed (non-console)
// Electron build is not reliably captured by a parent shell even when its
// stdout/stderr are redirected, which made an earlier silent-exit crash
// impossible to diagnose from outside the process. Written before anything
// else so it survives a failure during module load itself, not only inside
// app.whenReady().
const CRASH_LOG_PATH = path.join(os.tmpdir(), 'pdftranslate-main.log');
function fileLog(...args: unknown[]) {
  try {
    const line = `[${new Date().toISOString()}] ${args.map((a) => (a instanceof Error ? `${a.name}: ${a.message}\n${a.stack}` : String(a))).join(' ')}\n`;
    fs.appendFileSync(CRASH_LOG_PATH, line);
  } catch {
    // logging must never be the thing that crashes the app
  }
}
fileLog('main.ts module loading, pid', process.pid, 'argv', process.argv.join(' '));

const API_TOKEN = randomBytes(32).toString('base64url');
process.env.PDFTRANSLATE_API_TOKEN = API_TOKEN;

// Global EPIPE Guard
process.on('uncaughtException', (err) => {
  fileLog('uncaughtException', err);
  if ((err as NodeJS.ErrnoException).code === 'EPIPE') {
    return;
  }
  try {
    dialog.showErrorBox(
      'PDF Translate - Unexpected Error',
      `${err.name}: ${err.message}\n\n${err.stack}`
    );
  } catch {
    // dialog might not be ready yet
  }
});

process.on('unhandledRejection', (reason) => {
  fileLog('unhandledRejection', reason);
});

process.stdout?.on('error', () => {});
process.stderr?.on('error', () => {});

function getProjectRoot(): string {
  if (app.isPackaged) {
    return process.resourcesPath;
  } else {
    // Dev mode: __dirname = webui/frontend/dist-electron/
    // Go up 3 levels: dist-electron -> frontend -> webui -> vp-pdf root
    return path.resolve(__dirname, '..', '..', '..');
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
        path.join(PROJECT_ROOT, '.venv', 'Scripts', 'python.exe'),
        path.join(PROJECT_ROOT, 'python_runtime', 'python.exe'),
      ];
  const pythonExe = pythonCandidates.find((candidate) => fs.existsSync(candidate));
  const runServerScript = path.join(PROJECT_ROOT, 'webui', 'backend', 'run_server.py');
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
      `Không tìm thấy Python runtime tại .venv\\Scripts\\python.exe.\n\nĐã kiểm tra:\n${pythonCandidates.join('\n')}`
    );
    return;
  }

  if (!fs.existsSync(runServerScript)) {
    safeLog(`[FATAL] Server script not found: ${runServerScript}`);
    dialog.showErrorBox(
      'PDF Translate - Server Script Not Found',
      `Không tìm thấy file server:\n${runServerScript}`
    );
    return;
  }

  const backendEnvironment: NodeJS.ProcessEnv = {
    ...process.env,
    PDFTRANSLATE_API_TOKEN: API_TOKEN,
    PDFTRANSLATE_DATA_DIR: userDataPath,
  };

  pythonProcess = spawn(pythonExe, ['-s', runServerScript], {
    cwd: PROJECT_ROOT,
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: backendEnvironment,
    windowsHide: true,
  });

  pythonProcess.stdout?.on('data', (data) => {
    safeLog(`[Backend] ${data}`);
  });

  pythonProcess.stderr?.on('data', (data) => {
    safeLog(`[Backend ERR] ${data}`);
  });

  pythonProcess.stdout?.on('error', () => {});
  pythonProcess.stderr?.on('error', () => {});

  pythonProcess.on('error', (err) => {
    safeLog(`[Backend SPAWN ERROR] ${err.message}`);
    dialog.showErrorBox(
      'PDF Translate - Lỗi khởi động Backend',
      `Không thể khởi chạy máy chủ Python:\n${err.message}`
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
  win = new BrowserWindow({
    width: 1360,
    height: 880,
    title: 'PDF Translate',
    webPreferences: {
      preload: preloadPath,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      additionalArguments: [`--pdftranslate-api-token=${API_TOKEN}`],
    },
  });
  fileLog('BrowserWindow constructed');

  win.on('closed', () => fileLog('window closed event'));
  win.webContents.on('render-process-gone', (_event, details) => {
    fileLog('render-process-gone', JSON.stringify(details));
  });
  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    safeLog(`[Renderer] Failed to load: ${validatedURL} - ${errorCode} ${errorDescription}`);
  });
  win.webContents.on('did-finish-load', () => fileLog('did-finish-load'));

  const target = VITE_DEV_SERVER_URL ?? path.join(RENDERER_DIST, 'index.html');
  fileLog('loading renderer from', target, 'RENDERER_DIST exists =', fs.existsSync(RENDERER_DIST));
  if (VITE_DEV_SERVER_URL) {
    win.loadURL(VITE_DEV_SERVER_URL).catch((err) => fileLog('loadURL rejected', err));
  } else {
    win.loadFile(path.join(RENDERER_DIST, 'index.html')).catch((err) => fileLog('loadFile rejected', err));
  }
  fileLog('createWindow end (load call issued)');
}

ipcMain.handle('open-external', async (_event, url: string) => {
  if (typeof url === 'string' && (url.startsWith('http://') || url.startsWith('https://'))) {
    await shell.openExternal(url);
  }
});

app.on('window-all-closed', () => {
  fileLog('window-all-closed fired');
  intentionalShutdown = true;
  if (pythonProcess) {
    safeLog('Killing python backend process...');
    try {
      if (process.platform === 'win32' && pythonProcess.pid) {
        spawn('taskkill', ['/pid', String(pythonProcess.pid), '/f', '/t'], { windowsHide: true });
      } else {
        pythonProcess.kill('SIGTERM');
      }
    } catch (e) {
      safeLog('Error killing backend:', e);
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

app.whenReady().then(() => {
  fileLog('app ready, isPackaged =', app.isPackaged, 'resourcesPath =', process.resourcesPath);
  startPythonBackend();
  createWindow();
}).catch((err) => {
  fileLog('app.whenReady chain rejected', err);
});

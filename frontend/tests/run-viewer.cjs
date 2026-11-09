const { spawnSync } = require('node:child_process');
const path = require('node:path');

// Some development hosts set this globally, which starts Electron as Node
// and leaves BrowserWindow/app unavailable to the actual renderer tests.
const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;
const result = spawnSync(require('electron'), [path.join(__dirname, 'pdf-viewer.electron.cjs')], {
  env, stdio: 'inherit', windowsHide: true,
});
if (result.error) console.error(result.error);
process.exit(result.status ?? 1);

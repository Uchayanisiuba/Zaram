const { spawn } = require('child_process');
const path = require('path');

delete process.env.ELECTRON_RUN_AS_NODE;

const electronPath = path.join(__dirname, 'node_modules', 'electron', 'dist', 'electron.exe');
const args = ['.'];

const child = spawn(electronPath, args, {
  stdio: 'inherit',
  cwd: __dirname
});

child.on('close', (code) => {
  process.exit(code || 0);
});

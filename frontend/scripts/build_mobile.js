/**
 * Build the web bundle that is packaged into the Android app.
 *
 * The native build must never point at a local API, so the production URL is
 * baked in here — the development `.env.local` value never reaches the app.
 * Run it through `npm run mobile:build`.
 */
'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const PRODUCTION_API = 'https://clauseguard-api.onrender.com';

if (!process.env.REACT_APP_API_URL) {
  process.env.REACT_APP_API_URL = PRODUCTION_API;
}
process.env.REACT_APP_API_URL_MOBILE =
  process.env.REACT_APP_API_URL_MOBILE || PRODUCTION_API;

console.log(`Building the mobile bundle against ${process.env.REACT_APP_API_URL}`);

const reactScripts = path.join(__dirname, '..', 'node_modules', 'react-scripts', 'bin', 'react-scripts.js');
const result = spawnSync(process.execPath, [reactScripts, 'build'], {
  stdio: 'inherit',
  cwd: path.join(__dirname, '..'),
  env: process.env,
});

if (result.status !== 0) {
  process.exit(result.status === null ? 1 : result.status);
}

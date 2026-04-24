#!/usr/bin/env node

const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const SETUP_DEV_ENVIRONMENT = path.join(
  __dirname,
  'setup-dev-environment.js'
);
const PORTS_FILE = path.join(__dirname, '..', '.dev-ports.json');

function run(command, args) {
  return execFileSync(command, args, {
    cwd: path.join(__dirname, '..'),
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();
}

function getFrontendPort() {
  const fromEnv = process.env.FRONTEND_PORT?.trim();
  if (fromEnv) {
    const port = Number(fromEnv);
    if (Number.isInteger(port) && port > 0) {
      return port;
    }
  }

  try {
    if (fs.existsSync(PORTS_FILE)) {
      const data = JSON.parse(fs.readFileSync(PORTS_FILE, 'utf8'));
      const port = Number(data?.frontend);
      if (Number.isInteger(port) && port > 0) {
        return port;
      }
    }
  } catch (error) {
    throw new Error(`Failed to read saved dev ports: ${error.message}`);
  }

  const output = run(process.execPath, [SETUP_DEV_ENVIRONMENT, 'frontend']);
  const port = Number(output);

  if (!Number.isInteger(port) || port <= 0) {
    throw new Error(`Invalid frontend port: ${output}`);
  }

  return port;
}

function getTailnetHostname() {
  const fromEnv = process.env.TS_HOSTNAME?.trim();
  if (fromEnv) {
    return fromEnv.replace(/\.$/, '');
  }

  const output = run('tailscale', ['status', '--json']);
  const status = JSON.parse(output);
  const hostname = status?.Self?.DNSName;

  if (!hostname || typeof hostname !== 'string') {
    throw new Error('Could not determine Tailscale DNS name from tailscale status');
  }

  return hostname.replace(/\.$/, '');
}

function getPreviewOrigin() {
  const frontendPort = getFrontendPort();
  const hostname = getTailnetHostname();
  return `https://${hostname}:${frontendPort}`;
}

function printUsage() {
  console.log('Usage:');
  console.log('  node scripts/tailscale-preview.js origin');
  console.log('  node scripts/tailscale-preview.js env');
  console.log('  node scripts/tailscale-preview.js start');
  console.log('  node scripts/tailscale-preview.js stop');
}

function main() {
  const command = process.argv[2];
  const frontendPort = getFrontendPort();

  switch (command) {
    case 'origin':
      console.log(getPreviewOrigin());
      return;

    case 'env':
      console.log(`export VK_ALLOWED_ORIGINS="${getPreviewOrigin()}"`);
      return;

    case 'start':
      execFileSync(
        'tailscale',
        [
          'serve',
          '--bg',
          `--https=${frontendPort}`,
          `http://127.0.0.1:${frontendPort}`,
        ],
        {
          cwd: path.join(__dirname, '..'),
          stdio: 'inherit',
        }
      );
      return;

    case 'stop':
      execFileSync(
        'tailscale',
        ['serve', `--https=${frontendPort}`, 'off'],
        {
          cwd: path.join(__dirname, '..'),
          stdio: 'inherit',
        }
      );
      return;

    default:
      printUsage();
  }
}

main();

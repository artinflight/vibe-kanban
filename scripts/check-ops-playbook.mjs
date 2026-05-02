#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();

const requiredFiles = [
  'AGENTS.md',
  'README.md',
  'REPO_IDENTITY.md',
  'STATE.md',
  'STREAM.md',
  'HANDOFF.md',
  'DELTA.md',
  'docs/audits/vibe-kanban-ops-audit.md',
  'docs/operations/release-safety.md',
  'docs/operations/production-protections.md',
];

const errors = [];

for (const relPath of requiredFiles) {
  const fullPath = path.join(repoRoot, relPath);
  if (!fs.existsSync(fullPath)) {
    errors.push(`Missing required ops file: ${relPath}`);
  }
}

const readUtf8 = (relPath) =>
  fs.readFileSync(path.join(repoRoot, relPath), 'utf8');

if (errors.length === 0) {
  const agents = readUtf8('AGENTS.md');
  const readme = readUtf8('README.md');

  const requiredAgentRefs = [
    'STATE.md',
    'STREAM.md',
    'HANDOFF.md',
    'DELTA.md',
    'ops:check',
  ];

  for (const ref of requiredAgentRefs) {
    if (!agents.includes(ref)) {
      errors.push(`AGENTS.md must reference ${ref}`);
    }
  }

  const requiredReadmeRefs = [
    'REPO_IDENTITY.md',
    'STATE.md',
    'STREAM.md',
    'HANDOFF.md',
    'DELTA.md',
    'docs/operations/release-safety.md',
    'docs/operations/production-protections.md',
  ];

  for (const ref of requiredReadmeRefs) {
    if (!readme.includes(ref)) {
      errors.push(`README.md must reference ${ref}`);
    }
  }

  const releaseSafety = readUtf8('docs/operations/release-safety.md');
  const productionProtections = readUtf8(
    'docs/operations/production-protections.md'
  );
  const lightweightPreview = readUtf8(
    'docs/self-hosting/lightweight-agent-preview.mdx'
  );

  const includesNormalized = (text, ref) =>
    text.replace(/\s+/g, ' ').includes(ref.replace(/\s+/g, ' '));

  const productionGuardrailRefs = [
    'Do not restart `vibe-kanban.service`.',
    'Do not write, copy, move, chmod, replace, or delete anything under `/home/mcp/.local/bin/vibe-kanban*`.',
    'Do not edit `/home/mcp/.config/systemd/user/vibe-kanban.service*`.',
    'Do not use `/home/mcp/.local/share/vibe-kanban` as a test target.',
    'Do not deploy debug binaries into live production paths.',
    'operator explicitly approves the exact command first',
    '/home/mcp/.local/bin/vibe-kanban-serve-prod',
  ];

  for (const ref of productionGuardrailRefs) {
    if (!includesNormalized(agents, ref)) {
      errors.push(`AGENTS.md must include production guardrail: ${ref}`);
    }
    if (!includesNormalized(releaseSafety, ref)) {
      errors.push(
        `docs/operations/release-safety.md must include production guardrail: ${ref}`
      );
    }
    if (!includesNormalized(productionProtections, ref)) {
      errors.push(
        `docs/operations/production-protections.md must include production guardrail: ${ref}`
      );
    }
  }

  for (const ref of ['4311', '4312', 'Do not restart `vibe-kanban.service`.']) {
    if (!includesNormalized(lightweightPreview, ref)) {
      errors.push(
        `docs/self-hosting/lightweight-agent-preview.mdx must include preview guardrail: ${ref}`
      );
    }
  }
}

if (errors.length > 0) {
  console.error('Ops Playbook check failed:\n');
  for (const error of errors) {
    console.error(`- ${error}`);
  }
  process.exit(1);
}

console.log('Ops Playbook check passed.');

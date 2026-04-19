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
  'docs/standards/operating-model.md',
  'docs/standards/validation-and-automation.md',
  'docs/standards/documentation-and-continuity.md',
  'docs/standards/agent-rules.md',
  'docs/adoption/vibe-kanban-ops-adoption.md',
  'docs/operations/release-safety.md',
  'docs/operations/local-instance-qa-checklist.md',
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
    'docs/standards/operating-model.md',
    'docs/standards/validation-and-automation.md',
    'docs/adoption/vibe-kanban-ops-adoption.md',
    'docs/operations/release-safety.md',
    'docs/operations/local-instance-qa-checklist.md',
  ];

  for (const ref of requiredReadmeRefs) {
    if (!readme.includes(ref)) {
      errors.push(`README.md must reference ${ref}`);
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

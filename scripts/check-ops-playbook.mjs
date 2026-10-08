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
  const localContainer = readUtf8('crates/local-deployment/src/container.rs');
  const codexExecutor = readUtf8('crates/executors/src/executors/codex.rs');
  const workflow = readUtf8('VK_WORKFLOW.md');
  const runbook = readUtf8('VK_AGENT_DEPLOYMENT_RUNBOOK.md');

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
  ];

  for (const ref of requiredReadmeRefs) {
    if (!readme.includes(ref)) {
      errors.push(`README.md must reference ${ref}`);
    }
  }

  const queuedFollowUpConsumerCount = (
    localContainer.match(/consume_queued_follow_up\(&ctx\)\.await/g) ?? []
  ).length;
  if (queuedFollowUpConsumerCount < 3) {
    errors.push(
      'container.rs must consume queued follow-ups from normal finalization, skipped-cleanup finalization, and parallel setup completion'
    );
  }

  const skippedCleanupBlock = localContainer.match(
    /Skipping cleanup script for workspace[\s\S]*?already_finalized = true;/
  )?.[0];
  if (!skippedCleanupBlock?.includes('consume_queued_follow_up(&ctx).await')) {
    errors.push(
      'skipped-cleanup/no-op coding-agent path must consume queued follow-up before finalizing'
    );
  }

  if (
    !codexExecutor.includes('const DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS: usize = 8;')
  ) {
    errors.push(
      'codex executor default max active executions must stay above one; expected DEFAULT_CODEX_MAX_ACTIVE_EXECUTIONS = 8'
    );
  }

  for (const [name, contents] of [
    ['VK_WORKFLOW.md', workflow],
    ['VK_AGENT_DEPLOYMENT_RUNBOOK.md', runbook],
  ]) {
    if (!contents.includes('VK_CODEX_MAX_ACTIVE_EXECUTIONS=8')) {
      errors.push(
        `${name} must document VK_CODEX_MAX_ACTIVE_EXECUTIONS=8 as a required live runtime guardrail`
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

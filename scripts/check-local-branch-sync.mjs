#!/usr/bin/env node

import { execFileSync } from 'node:child_process';

const branchPairs = [
  ['staging', 'fork/staging'],
  ['main', 'origin/main'],
];

const runGit = (...args) =>
  execFileSync('git', args, {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim();

const resolveRef = (ref) => {
  try {
    return runGit('rev-parse', '--verify', ref);
  } catch (error) {
    return null;
  }
};

const summarizeDivergence = (localRef, remoteRef) => {
  try {
    return runGit(
      'log',
      '--oneline',
      '--left-right',
      `${localRef}...${remoteRef}`,
      '--',
    )
      .split('\n')
      .filter(Boolean)
      .slice(0, 10);
  } catch (error) {
    return [];
  }
};

const errors = [];

for (const [localRef, remoteRef] of branchPairs) {
  const localSha = resolveRef(localRef);
  const remoteSha = resolveRef(remoteRef);

  if (!localSha || !remoteSha) {
    errors.push(
      `Unable to resolve ${localRef} or ${remoteRef}. Fetch the remotes and make sure both refs exist locally.`,
    );
    continue;
  }

  if (localSha === remoteSha) {
    continue;
  }

  const commits = summarizeDivergence(localRef, remoteRef);
  const summary = commits.length
    ? `Recent divergence:\n${commits.join('\n')}`
    : 'Recent divergence: unavailable';

  errors.push(
    [
      `Canonical branch sync failed for ${localRef}.`,
      `${localRef}: ${localSha}`,
      `${remoteRef}: ${remoteSha}`,
      summary,
      `Repair ${localRef} before using it as a branch base or describing the canonical checkout as healthy.`,
    ].join('\n'),
  );
}

if (errors.length > 0) {
  console.error(errors.join('\n\n'));
  process.exit(1);
}

console.log(
  'Canonical branch sync OK: local staging matches fork/staging and local main matches origin/main.',
);

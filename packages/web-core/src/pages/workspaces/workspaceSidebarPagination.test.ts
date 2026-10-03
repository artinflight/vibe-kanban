import assert from 'node:assert/strict';
import { test } from 'node:test';
import { paginateWorkspaceSidebar } from './workspaceSidebarPagination.ts';

const idle = Array.from({ length: 50 }, (_, index) => ({
  id: `idle-${index}`,
}));
const actionable = [
  { id: 'unread', hasUnseenActivity: true },
  { id: 'running', isRunning: true },
  { id: 'approval', hasPendingApproval: true },
  { id: 'subagent', activeSubagentCount: 1 },
  { id: 'unresolved', unresolvedSubagentCount: 1 },
];

test('accordion retains actionable work beyond the idle history page', () => {
  const rows = [...idle, ...actionable, { id: 'older-idle' }];
  assert.deepEqual(
    paginateWorkspaceSidebar(rows, 50, false, true).map((row) => row.id),
    [...idle, ...actionable].map((row) => row.id)
  );
});

test('flat layout retains ordinary pagination and search returns all matches', () => {
  const rows = [...idle, ...actionable];
  assert.deepEqual(paginateWorkspaceSidebar(rows, 50, false, false), idle);
  assert.equal(paginateWorkspaceSidebar(rows, 50, true, false), rows);
});

test('loading more preserves sort order and does not duplicate priority entries', () => {
  const rows = [...idle, ...actionable, { id: 'older-idle' }];
  assert.deepEqual(paginateWorkspaceSidebar(rows, 56, false, true), rows);
});

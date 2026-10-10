import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  filterWorkspaceAssignments,
  workspaceAssigneesById,
  type WorkspaceAssignmentFilter,
} from './workspaceAssignmentFilter.ts';
import { paginateWorkspaceSidebar } from './workspaceSidebarPagination.ts';

const seamus = 'seamus-id';
const dot = 'dot-id';
const rows = [
  'dot-only',
  'shared',
  'seamus-only',
  'unassigned',
  'unlinked',
  'historical',
].map((id) => ({
  id,
  hasUnseenActivity: true,
  isPinned: true,
}));
const links = [
  { workspace_id: 'dot-only', issue_id: 'dot-task', user_id: dot },
  { workspace_id: 'shared', issue_id: 'shared-task', user_id: dot },
  { workspace_id: 'shared', issue_id: 'shared-task', user_id: seamus },
  { workspace_id: 'seamus-only', issue_id: 'seamus-task', user_id: seamus },
  { workspace_id: 'unassigned', issue_id: 'unassigned-task', user_id: null },
  { workspace_id: 'unlinked', issue_id: null, user_id: null },
];
const byId = workspaceAssigneesById(links);
const ids = (filter: WorkspaceAssignmentFilter, user = seamus) =>
  filterWorkspaceAssignments(rows, filter, user, byId).map((w) => w.id);

test('Mine excludes dot-only work including pinned/unread items; shared, Seamus and historical remain', () => {
  assert.deepEqual(ids('mine'), [
    'shared',
    'seamus-only',
    'unassigned',
    'unlinked',
    'historical',
  ]);
  assert.deepEqual(ids('mine', dot), [
    'dot-only',
    'shared',
    'unassigned',
    'unlinked',
    'historical',
  ]);
});

test('switching Mine → All → Mine is reversible and preserves unread and object identity', () => {
  const before = JSON.stringify(rows);
  assert.equal(ids('mine').length, 5);
  assert.equal(filterWorkspaceAssignments(rows, 'all', seamus, byId), rows);
  assert.equal(ids('all').length, 6);
  assert.equal(ids('mine').length, 5);
  assert.equal(JSON.stringify(rows), before);
  assert.equal(
    filterWorkspaceAssignments(rows, 'mine', seamus, byId)[0],
    rows[1]
  );
});

test('assignment filtering precedes pagination, activity grouping and counts for active and archived lists', () => {
  for (const archived of [false, true]) {
    const input = rows.map((row) => ({ ...row, isArchived: archived }));
    const mine = filterWorkspaceAssignments(input, 'mine', seamus, byId);
    assert.equal(mine.length, 5);
    assert.deepEqual(
      paginateWorkspaceSidebar(mine, 2, false, false).map((w) => w.id),
      ['shared', 'seamus-only']
    );
    assert.equal(paginateWorkspaceSidebar(mine, 2, false, true).length, 5);
    assert.equal(mine.filter((w) => w.hasUnseenActivity).length, 5);
    assert.equal(
      filterWorkspaceAssignments(input, 'all', seamus, byId).length,
      6
    );
  }
});

test('unknown identity or unavailable assignment data preserves visibility', () => {
  assert.equal(filterWorkspaceAssignments(rows, 'mine', null, byId), rows);
  assert.deepEqual(
    filterWorkspaceAssignments(rows, 'mine', seamus, new Map()),
    rows
  );
});

test('assignment refresh and unlinking immediately recompute inherited visibility', () => {
  const shared = workspaceAssigneesById([
    ...links,
    { workspace_id: 'dot-only', issue_id: 'dot-task', user_id: seamus },
  ]);
  assert.equal(
    filterWorkspaceAssignments(rows, 'mine', seamus, shared).length,
    6
  );
  const removed = workspaceAssigneesById(
    links.filter((link) => link.workspace_id !== 'dot-only')
  );
  assert.equal(
    filterWorkspaceAssignments(rows, 'mine', seamus, removed).length,
    6
  );
  assert.equal(ids('mine').length, 5);
});

test('every workspace of the same issue inherits its multi-assignees', () => {
  const assignments = workspaceAssigneesById([
    ...links,
    {
      workspace_id: 'second-shared-workspace',
      issue_id: 'shared-task',
      user_id: dot,
    },
    {
      workspace_id: 'second-shared-workspace',
      issue_id: 'shared-task',
      user_id: seamus,
    },
  ]);
  assert.equal(
    filterWorkspaceAssignments(
      [{ id: 'second-shared-workspace' }],
      'mine',
      seamus,
      assignments
    ).length,
    1
  );
});

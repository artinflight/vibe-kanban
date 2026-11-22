import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  workspaceSidebarSections,
  type SidebarActivity,
} from '../../packages/ui/src/lib/workspaceSidebarSections.ts';

for (const activity of [
  { isRunning: true },
  { activeSubagentCount: 1 },
  { unresolvedSubagentCount: 1 },
]) {
  test(`saved activity stays in Running: ${Object.keys(activity)[0]}`, () => {
    const workspace = Object.freeze({
      id: 'saved',
      readLater: true,
      hasUnseenActivity: true,
      dotUnreadCount: 3,
      hasPendingApproval: true,
      dotNeedsAttentionCount: 1,
      ...activity,
    });
    const groups = workspaceSidebarSections([workspace]);
    assert.deepEqual(groups.runningWorkspaces, [workspace]);
    assert.deepEqual(groups.readLaterWorkspaces, []);
    assert.deepEqual(groups.raisedHandWorkspaces, []);
    assert.deepEqual(groups.idleWorkspaces, []);
    assert.equal(groups.runningWorkspaces[0], workspace);
    assert.equal(workspace.readLater, true);

    const stopped = {
      ...workspace,
      isRunning: false,
      activeSubagentCount: 0,
      unresolvedSubagentCount: 0,
    };
    const settled = workspaceSidebarSections([stopped]);
    assert.deepEqual(settled.runningWorkspaces, []);
    assert.deepEqual(settled.readLaterWorkspaces, [stopped]);
    assert.deepEqual(settled.raisedHandWorkspaces, []);
    assert.deepEqual(settled.idleWorkspaces, []);
  });
}

test('parent stopping keeps saved work running until subagent activity settles', () => {
  const workspace = {
    readLater: true,
    isRunning: true,
    activeSubagentCount: 1,
    unresolvedSubagentCount: 0,
  };
  for (const state of [
    workspace,
    { ...workspace, isRunning: false },
    {
      ...workspace,
      isRunning: false,
      activeSubagentCount: 0,
      unresolvedSubagentCount: 1,
    },
  ]) {
    const groups = workspaceSidebarSections([state]);
    assert.deepEqual(groups.runningWorkspaces, [state]);
    assert.deepEqual(groups.readLaterWorkspaces, []);
  }
});

for (const attention of [
  {},
  { hasUnseenActivity: true },
  { dotUnreadCount: 2 },
  { hasPendingApproval: true },
  { dotNeedsAttentionCount: 1 },
] satisfies SidebarActivity[]) {
  test(`removing a running bookmark restores normal stop grouping: ${Object.keys(attention)[0] ?? 'read'}`, () => {
    const saved = { ...attention, isRunning: true, readLater: true };
    const unsaved = { ...saved, readLater: false };
    const running = workspaceSidebarSections([unsaved]);
    assert.deepEqual(running.runningWorkspaces, [unsaved]);
    assert.deepEqual(running.readLaterWorkspaces, []);

    const stopped = { ...unsaved, isRunning: false };
    const groups = workspaceSidebarSections([stopped]);
    assert.deepEqual(groups.runningWorkspaces, []);
    assert.deepEqual(groups.readLaterWorkspaces, []);
    assert.deepEqual(
      groups.raisedHandWorkspaces,
      Object.keys(attention).length ? [stopped] : []
    );
    assert.deepEqual(
      groups.idleWorkspaces,
      Object.keys(attention).length ? [] : [stopped]
    );

    const stillSaved = { ...saved, isRunning: false };
    assert.deepEqual(
      workspaceSidebarSections([stillSaved]).readLaterWorkspaces,
      [stillSaved]
    );
  });
}

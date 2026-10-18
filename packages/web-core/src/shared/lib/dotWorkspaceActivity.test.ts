import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  workspaceDotNotification,
  workspaceDotManaged,
  type DotManagedWorkspace,
} from './dotWorkspaceActivity.ts';

const aggregate = {
  project_id: 'p',
  issue_id: 'i',
  unread_count: 2,
  needs_attention_count: 1,
  shared_unread_count: 1,
  shared_needs_attention_count: 1,
};
const dispatch = {
  project_id: 'p',
  issue_id: 'i',
  workspace_id: 'target',
  unread_count: 1,
  needs_attention_count: 0,
};

test('target adds dispatch; siblings retain only the genuine shared conversation', () => {
  assert.equal(
    workspaceDotNotification('i', aggregate, dispatch)?.unread_count,
    2
  );
  assert.equal(workspaceDotNotification('i', aggregate)?.unread_count, 1);
  assert.equal(
    workspaceDotNotification('i', aggregate)?.needs_attention_count,
    1
  );
  assert.equal(aggregate.unread_count, 2, 'Issue aggregate remains intact');
});
test('dispatch-only thread produces no sibling badge without mutating read state', () => {
  const onlyNote = {
    ...aggregate,
    unread_count: 1,
    needs_attention_count: 0,
    shared_unread_count: 0,
    shared_needs_attention_count: 0,
  };
  assert.equal(
    workspaceDotNotification('i', onlyNote, dispatch)?.unread_count,
    1
  );
  assert.equal(workspaceDotNotification('i', onlyNote)?.unread_count, 0);
  assert.equal(
    workspaceDotNotification('i', onlyNote)?.needs_attention_count,
    0
  );
});
test('legacy service, dispatch-only lookup, relink and unlinked workspaces', () => {
  const legacy = {
    project_id: 'p',
    issue_id: 'i',
    unread_count: 2,
    needs_attention_count: 1,
  };
  assert.equal(workspaceDotNotification('i', legacy)?.unread_count, 2);
  assert.equal(
    workspaceDotNotification('i', undefined, dispatch)?.unread_count,
    1
  );
  assert.equal(
    workspaceDotNotification('new-issue', undefined, dispatch),
    undefined
  );
  assert.equal(workspaceDotNotification(null, aggregate, dispatch), undefined);
  assert.equal(workspaceDotNotification('i'), undefined);
});

test('explicit dispatch attention is additive only on its target', () => {
  assert.equal(
    workspaceDotNotification('i', aggregate, {
      ...dispatch,
      needs_attention_count: 1,
    })?.needs_attention_count,
    2
  );
  assert.equal(
    workspaceDotNotification('i', aggregate)?.needs_attention_count,
    1
  );
});

test('management requires an explicit exact association, independent of counts', () => {
  const association: DotManagedWorkspace = {
    workspace_id: 'target',
    issue_id: 'i',
    project_id: 'p',
    manager: 'dot',
    state: 'managed',
  };
  assert.equal(workspaceDotManaged('target', 'i', association), true);
  assert.equal(workspaceDotManaged('sibling', 'i', association), false);
  assert.equal(workspaceDotManaged('target', 'relinked', association), false);
  assert.equal(workspaceDotManaged('target', null, association), false);
  assert.equal(workspaceDotManaged('target', 'i'), false);
  // Generic Dot dispatch/count metadata cannot establish a management relation.
  assert.equal(
    workspaceDotManaged(
      'target',
      'i',
      dispatch as unknown as DotManagedWorkspace
    ),
    false
  );
  for (const changes of [{ state: 'released' }, { manager: 'unknown' }]) {
    assert.equal(
      workspaceDotManaged('target', 'i', {
        ...association,
        ...changes,
      } as DotManagedWorkspace),
      false
    );
  }
});

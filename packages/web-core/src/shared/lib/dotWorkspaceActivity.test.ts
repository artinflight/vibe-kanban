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

test('only explicit target rows badge workspaces; shared history does not fan out', () => {
  assert.equal(
    workspaceDotNotification('i', aggregate, dispatch)?.unread_count,
    1
  );
  assert.equal(workspaceDotNotification('i', aggregate)?.unread_count, 0);
  assert.equal(
    workspaceDotNotification('i', aggregate)?.needs_attention_count,
    0
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
  assert.equal(workspaceDotNotification('i', legacy)?.unread_count, 0);
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
  assert.equal(
    workspaceDotNotification('project:p', aggregate, dispatch),
    undefined
  );
});

test('explicit attention remains independent only on its target', () => {
  assert.equal(
    workspaceDotNotification('i', aggregate, {
      ...dispatch,
      needs_attention_count: 1,
    })?.needs_attention_count,
    1
  );
  assert.equal(
    workspaceDotNotification('i', aggregate)?.needs_attention_count,
    0
  );
});

test('new substantive target message after cleanup never recreates four sibling badges', () => {
  // No dispatch receipt is involved; stale issue totals cannot create a target.
  for (const [unread, attention] of [
    [1, 0],
    [1, 1],
    [0, 1],
    [1, 1],
    [0, 0],
  ]) {
    const target = {
      ...dispatch,
      unread_count: unread,
      needs_attention_count: attention,
    };
    const actual = workspaceDotNotification('i', aggregate, target);
    assert.equal(actual?.unread_count, unread);
    assert.equal(actual?.needs_attention_count, attention);
    for (const siblingId of ['B', 'C', 'D', 'E']) {
      const sibling = workspaceDotNotification('i', aggregate);
      assert.equal(sibling?.unread_count, 0, siblingId);
      assert.equal(sibling?.needs_attention_count, 0, siblingId);
    }
  }
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

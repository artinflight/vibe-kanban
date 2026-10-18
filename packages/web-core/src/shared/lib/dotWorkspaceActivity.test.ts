import assert from 'node:assert/strict';
import { test } from 'node:test';
import { workspaceDotNotification } from './dotWorkspaceActivity.ts';

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

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { useCreateWorkspace } from '../../packages/web-core/src/shared/hooks/useCreateWorkspace';
import { state } from './workspace-creation.fixture';

test('a local inbox issue must not suppress the requested remote issue link', async () => {
  state.links = [];
  state.workspace.task_id = 'inbox-issue';
  const before = JSON.stringify(state.workspace);
  const { createWorkspace } = useCreateWorkspace();
  const result = await createWorkspace.mutationFn({
    data: {},
    linkToIssue: { remoteProjectId: 'requested-project', issueId: 'requested-issue' },
  });
  assert.deepEqual(state.links, [['workspace-id', 'requested-project', 'requested-issue']]);
  assert.equal(result.workspace, state.workspace);
  assert.equal(JSON.stringify(state.workspace), before);
});

test('a matching local issue is already linked and is not linked twice', async () => {
  state.links = [];
  state.workspace.task_id = 'requested-issue';
  const { createWorkspace } = useCreateWorkspace();
  await createWorkspace.mutationFn({
    data: {},
    linkToIssue: { remoteProjectId: 'requested-project', issueId: 'requested-issue' },
  });
  assert.deepEqual(state.links, []);
  assert.equal(state.workspace.has_unseen_turns, true);
});

test('standalone creation retains the durable inbox issue', async () => {
  state.links = [];
  state.workspace.task_id = 'inbox-issue';
  const { createWorkspace } = useCreateWorkspace();
  const result = await createWorkspace.mutationFn({ data: {} });
  assert.equal(result.workspace.task_id, 'inbox-issue');
  assert.deepEqual(state.links, []);
});

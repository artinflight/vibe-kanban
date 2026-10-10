import React from 'react';
import Renderer, { act } from 'react-test-renderer';
import assert from 'node:assert/strict';
import { after, afterEach, beforeEach, test } from 'node:test';
import { MessageChannel as NodeMessageChannel } from 'node:worker_threads';
import { KanbanIssuePanelContainer } from '../../packages/web-core/src/pages/kanban/KanbanIssuePanelContainer';
import { KanbanIssuePanel } from '../../packages/ui/src/components/KanbanIssuePanel';
import {
  useKanbanIssueComposer,
  useKanbanIssueComposerStore as store,
  openKanbanIssueComposer,
  patchKanbanIssueComposer,
} from '../../packages/web-core/src/shared/stores/useKanbanIssueComposerStore';
import { useKanbanIssueComposerScratch } from '../../packages/web-core/src/shared/hooks/useKanbanIssueComposerScratch';
import { state, issue } from './kanban-issue-panel.fixture';

// Bundled React's async act uses its browser MessageChannel fallback. Close the
// channels after every act/renderer cleanup has settled so Node can exit normally.
const channels = new Set<NodeMessageChannel>();
globalThis.MessageChannel = class extends NodeMessageChannel {
  constructor() {
    super();
    channels.add(this);
  }
} as unknown as typeof globalThis.MessageChannel;
after(() => {
  for (const channel of channels) {
    channel.port1.close();
    channel.port2.close();
  }
});

const key = 'local:p';
let tree: Renderer.ReactTestRenderer;
let beforeIssue: string;
let consoleError: typeof console.error;
const errors: unknown[][] = [];
const storage = new Map<string, string>();

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function Host() {
  const composer = useKanbanIssueComposer(key);
  return (
    <>
      <button
        aria-label="New issue"
        onClick={() =>
          openKanbanIssueComposer(key, { assigneeIds: ['dot', 'seamus'] })
        }
      />
      {composer && (
        <KanbanIssuePanelContainer
          issueResolution="ready"
          onExpectIssueOpen={(id) => state.expected.push(id)}
        />
      )}
    </>
  );
}

const panel = () => tree.root.findByType(KanbanIssuePanel);
const entry = () => store.getState().byKey[key]!;
const tick = () => new Promise((resolve) => setImmediate(resolve));
async function reopen() {
  await act(async () => {
    tree.root.findByProps({ 'aria-label': 'New issue' }).props.onClick();
  });
}
async function dismiss(method: 'X' | 'Escape') {
  await act(async () => {
    if (method === 'X') {
      tree.root
        .findByProps({ 'aria-label': 'kanban.closePanel' })
        .props.onClick();
    } else {
      tree.root
        .findAllByType('div')
        .find((node) => node.props.className?.startsWith('mobile-task-detail'))!
        .props.onKeyDown({ key: 'Escape', target: { tagName: 'DIV' } });
    }
  });
  assert.equal(tree.root.findAllByType(KanbanIssuePanel).length, 0);
}
async function submit() {
  let pending!: Promise<void>;
  await act(async () => {
    pending = panel().props.onSubmit();
    await tick();
  });
  return { pending };
}

beforeEach(async () => {
  consoleError = console.error;
  console.error = (...args) => {
    errors.push(args);
  };
  errors.length = 0;
  beforeIssue = JSON.stringify(issue);
  globalThis.document = {
    activeElement: null,
    addEventListener() {},
    removeEventListener() {},
  } as unknown as Document;
  globalThis.window = {
    setTimeout,
    clearTimeout,
    matchMedia: () => ({
      matches: false,
      addEventListener() {},
      removeEventListener() {},
    }),
  } as unknown as Window & typeof globalThis;
  globalThis.localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => {
      storage.set(key, value);
    },
    removeItem: (key) => {
      storage.delete(key);
    },
  } as Storage;
  storage.clear();
  Object.assign(state, {
    creates: 0,
    calls: [],
    navigations: [],
    expected: [],
    editCalls: 0,
    issueId: null,
    wait: null,
    issueWait: null,
    workspaceWait: null,
    scratchWait: null,
    scratchRequests: [],
    scratchWrites: [],
    failDot: false,
    runtime: 'local',
  });
  store.setState({ byKey: {} });
  openKanbanIssueComposer(key, { assigneeIds: ['dot', 'seamus'] });
  patchKanbanIssueComposer(key, { title: 'Dot task' });
  await act(async () => {
    tree = Renderer.create(<Host />);
  });
});

afterEach(async () => {
  await act(async () => {
    tree?.unmount();
  });
  console.error = consoleError;
  assert.equal(
    JSON.stringify(issue),
    beforeIssue,
    'unread and saved issue untouched'
  );
  assert.ok(
    errors.every((args) => args[0] === 'Failed to save issue:'),
    'unexpected React/render error: ' +
      errors.map((args) => String(args[0]) + ' ' + String(args[1])).join('\n')
  );
});

for (const method of ['X', 'Escape'] as const) {
  test(`${method}/reopen while issue POST is delayed retains identity and prevents a second create`, async () => {
    const gate = deferred<typeof issue>();
    state.issueWait = gate.promise;
    const id = entry().id;
    const { pending } = await submit();
    await dismiss(method);
    assert.equal(entry().id, id);
    assert.equal(entry().isOpen, false);
    assert.equal(entry().submissionPending, true);
    await reopen();
    assert.equal(entry().id, id);
    assert.equal(panel().props.isSubmitting, true);
    await act(async () => {
      await panel().props.onSubmit();
    });
    assert.equal(state.creates, 1);
    await act(async () => {
      gate.resolve(issue);
      await pending;
    });
    assert.deepEqual(state.calls, [
      ['created', 'dot'],
      ['created', 'seamus'],
    ]);
    assert.deepEqual(state.expected, ['created']);
    assert.deepEqual(state.navigations, ['closed', 'created']);
    assert.equal(store.getState().byKey[key], undefined);
  });

  test(`${method}/reopen while assignment POST is delayed keeps confirmed participants and prevents duplicate requests`, async () => {
    const gate = deferred<void>();
    state.wait = gate.promise;
    const id = entry().id;
    const { pending } = await submit();
    assert.deepEqual(entry().submission?.completedAssigneeIds, ['dot']);
    await dismiss(method);
    await reopen();
    assert.equal(entry().id, id);
    assert.equal(entry().submission?.issue?.id, 'created');
    await act(async () => {
      await panel().props.onSubmit();
    });
    assert.equal(state.creates, 1);
    assert.equal(state.calls.length, 2);
    await act(async () => {
      gate.resolve();
      await pending;
    });
    assert.equal(state.calls.length, 2);
    assert.deepEqual(state.expected, ['created']);
  });

  test(`${method} after partial failure retains recovery and retries only the failed participant`, async () => {
    state.failDot = true;
    const id = entry().id;
    const { pending } = await submit();
    await act(async () => {
      await pending;
    });
    assert.ok(tree.root.findByProps({ role: 'alert' }));
    await dismiss(method);
    assert.equal(entry().id, id);
    assert.equal(entry().submissionPending, false);
    assert.deepEqual(entry().submission?.completedAssigneeIds, ['seamus']);
    await reopen();
    assert.equal(entry().id, id);
    assert.ok(tree.root.findByProps({ role: 'alert' }));
    assert.equal(panel().props.formData.title, 'Dot task');
    state.failDot = false;
    await act(async () => {
      await panel().props.onSubmit();
    });
    assert.equal(state.creates, 1);
    assert.deepEqual(state.calls, [
      ['created', 'dot'],
      ['created', 'seamus'],
      ['created', 'dot'],
    ]);
    assert.deepEqual(state.expected, ['created']);
  });
}

test('assignment failure arriving after dismissal remains recoverable on reopen', async () => {
  const gate = deferred<void>();
  state.wait = gate.promise;
  state.failDot = true;
  const id = entry().id;
  const { pending } = await submit();
  await dismiss('X');
  await act(async () => {
    gate.resolve();
    await pending;
  });
  assert.equal(entry().id, id);
  assert.equal(entry().isOpen, false);
  assert.equal(entry().submissionPending, false);
  assert.deepEqual(entry().submission?.completedAssigneeIds, ['seamus']);
  assert.deepEqual(state.expected, []);
  await reopen();
  assert.ok(tree.root.findByProps({ role: 'alert' }));
  state.failDot = false;
  await act(async () => {
    await panel().props.onSubmit();
  });
  assert.equal(state.creates, 1);
  assert.deepEqual(state.calls, [
    ['created', 'dot'],
    ['created', 'seamus'],
    ['created', 'dot'],
  ]);
});

test('successful background completion stays dismissed and the next composer has a fresh identity', async () => {
  const gate = deferred<typeof issue>();
  state.issueWait = gate.promise;
  const id = entry().id;
  const { pending } = await submit();
  await dismiss('X');
  await act(async () => {
    gate.resolve(issue);
    await pending;
  });
  assert.deepEqual(state.navigations, ['closed']);
  assert.deepEqual(state.expected, []);
  assert.equal(store.getState().byKey[key], undefined);
  await reopen();
  assert.notEqual(entry().id, id);
  assert.equal(entry().submission, undefined);
  assert.equal(entry().submissionPending, undefined);
});

for (const stage of ['issue', 'assignment'] as const) {
  test(`late ${stage} completion cannot checkpoint, unlock, close or navigate a replacement composer`, async () => {
    const issueGate = deferred<typeof issue>();
    const assignmentGate = deferred<void>();
    if (stage === 'issue') state.issueWait = issueGate.promise;
    else state.wait = assignmentGate.promise;
    const oldId = entry().id;
    const { pending } = await submit();
    await dismiss('Escape');
    // Simulate a superseding store/hydration entry to exercise the identity fence,
    // even though ordinary reopen must retain the original pending identity.
    await act(async () => {
      store.setState({ byKey: {} });
      openKanbanIssueComposer(key, {});
      patchKanbanIssueComposer(key, { title: 'Replacement' });
      assert.ok(store.getState().beginSubmission(key, entry().id));
    });
    const replacement = entry();
    assert.notEqual(replacement.id, oldId);
    await act(async () => {
      issueGate.resolve(issue);
      assignmentGate.resolve();
      await pending;
    });
    assert.equal(entry(), replacement);
    assert.equal(entry().submissionPending, true);
    assert.equal(entry().submission, undefined);
    assert.equal(entry().draft.title, 'Replacement');
    assert.deepEqual(state.navigations, ['closed']);
    assert.deepEqual(state.expected, []);
    // Explicit old cleanup/dismissal must also be harmless.
    await act(async () => {
      store.getState().closeComposer(key, oldId);
      assert.equal(store.getState().finishSubmission(key, oldId), false);
    });
    assert.equal(entry(), replacement);
  });
}

test('editing an issue while recovery is dismissed preserves the edit picker and hidden recovery', async () => {
  state.failDot = true;
  const { pending } = await submit();
  await act(async () => {
    await pending;
  });
  await dismiss('X');
  const recovery = entry();
  state.issueId = 'created';
  await act(async () => {
    tree.unmount();
    tree = Renderer.create(
      <KanbanIssuePanelContainer
        issueResolution="ready"
        onExpectIssueOpen={() => {}}
      />
    );
  });
  assert.equal(panel().props.mode, 'edit');
  assert.equal(panel().props.isFormLocked, false);
  assert.equal(panel().props.isSubmitting, false);
  await act(async () => {
    await panel().props.onFormChange('assigneeIds', []);
  });
  assert.equal(state.editCalls, 1);
  await act(async () => {
    tree.root
      .findByProps({ 'aria-label': 'kanban.closePanel' })
      .props.onClick();
  });
  assert.equal(entry(), recovery);
});

test('legacy remote draft hydration assigns an identity and clears stale pending state', async () => {
  await act(async () => {
    tree.unmount();
  });
  store.setState({ byKey: {} });
  state.runtime = 'remote';
  storage.set(
    'vk-kanban-issue-composer',
    JSON.stringify({
      [key]: {
        initial: { title: '', description: null },
        draft: { title: 'Legacy draft', description: null },
        submissionPending: true,
      },
    })
  );
  function Hydrate() {
    useKanbanIssueComposerScratch();
    return null;
  }
  await act(async () => {
    tree = Renderer.create(<Hydrate />);
  });
  assert.ok(entry().id);
  assert.equal(entry().isOpen, true);
  assert.equal(entry().submissionPending, false);
  assert.equal(entry().draft.title, 'Legacy draft');
});

for (const method of ['X', 'Escape'] as const) {
  test(`${method} during real workspace scratch persistence blocks navigation and retains saved recovery`, async () => {
    await act(async () => {
      await panel().props.onFormChange('createDraftWorkspace', true);
    });
    const gate = deferred<void>();
    state.scratchWait = gate.promise;
    const id = entry().id;
    const { pending } = await submit();
    assert.equal(state.scratchRequests.length, 1);
    assert.equal(state.scratchWrites.length, 0);
    assert.deepEqual(entry().submission?.completedAssigneeIds, [
      'dot',
      'seamus',
    ]);
    await dismiss(method);
    await act(async () => {
      gate.resolve();
      await pending;
    });
    assert.deepEqual(state.navigations, ['closed']);
    assert.deepEqual(state.expected, []);
    assert.equal(
      state.scratchWrites.length,
      1,
      'saved draft remains available'
    );
    assert.equal(entry().id, id);
    assert.equal(entry().isOpen, false);
    assert.equal(entry().submissionPending, false);
    assert.equal(entry().submission?.issue?.id, 'created');
    await reopen();
    await act(async () => {
      await panel().props.onSubmit();
    });
    assert.equal(state.creates, 1, 'recovery uses the saved issue');
    assert.deepEqual(state.calls, [
      ['created', 'dot'],
      ['created', 'seamus'],
    ]);
    assert.deepEqual(state.navigations, [
      'closed',
      ['workspace', 'p', 'created', state.scratchWrites[1].id],
    ]);
    assert.equal(store.getState().byKey[key], undefined);
  });
}

test('delayed real scratch write cannot navigate or mutate a replacement composer', async () => {
  await act(async () => {
    await panel().props.onFormChange('createDraftWorkspace', true);
  });
  const gate = deferred<void>();
  state.scratchWait = gate.promise;
  const oldId = entry().id;
  const { pending } = await submit();
  assert.equal(state.scratchRequests.length, 1);
  await dismiss('X');
  await act(async () => {
    store.setState({ byKey: {} });
    openKanbanIssueComposer(key, {});
    patchKanbanIssueComposer(key, { title: 'Replacement' });
    assert.ok(store.getState().beginSubmission(key, entry().id));
  });
  const replacement = entry();
  assert.notEqual(replacement.id, oldId);
  await act(async () => {
    gate.resolve();
    await pending;
  });
  assert.equal(state.scratchWrites.length, 1);
  assert.equal(entry(), replacement);
  assert.equal(entry().submissionPending, true);
  assert.equal(entry().submission, undefined);
  assert.equal(entry().draft.title, 'Replacement');
  assert.deepEqual(state.navigations, ['closed']);
  assert.deepEqual(state.expected, []);
  assert.equal(state.creates, 1);
  assert.equal(state.calls.length, 2);
});

test('ordinary workspace creation navigates once after the real linked scratch write succeeds', async () => {
  await act(async () => {
    await panel().props.onFormChange('createDraftWorkspace', true);
  });
  const gate = deferred<void>();
  state.scratchWait = gate.promise;
  const { pending } = await submit();
  assert.equal(state.scratchRequests.length, 1);
  assert.equal(state.scratchWrites.length, 0);
  assert.deepEqual(state.navigations, []);
  await act(async () => {
    gate.resolve();
    await pending;
  });
  const scratch = state.scratchWrites[0];
  assert.equal(scratch.type, 'DRAFT_WORKSPACE');
  assert.equal(scratch.payload.type, 'DRAFT_WORKSPACE');
  assert.equal(scratch.payload.data.message, 'Dot task');
  assert.deepEqual(scratch.payload.data.linked_issue, {
    issue_id: 'created',
    simple_id: 'T1',
    title: 'Dot task',
    remote_project_id: 'p',
  });
  assert.deepEqual(state.navigations, [
    ['workspace', 'p', 'created', scratch.id],
  ]);
  assert.equal(store.getState().byKey[key], undefined);
  assert.equal(state.creates, 1);
  assert.equal(state.calls.length, 2);
});

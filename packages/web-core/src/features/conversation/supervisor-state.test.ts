import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  applySupervisorEvent,
  mergeMessages,
  mergeRuns,
} from './supervisor-state.ts';
import type { SupervisorHistory } from './supervisor-state.ts';
import type {
  ConversationMessage,
  SupervisorEvent,
} from '../../../../../shared/types.ts';

const message = (
  id: string,
  seq: number,
  revision = 1
): ConversationMessage => ({
  id,
  conversation_id: 'conversation',
  created_seq: seq,
  revision,
  role: 'assistant',
  origin: 'derived',
  body: 'The agent needs your decision.',
  status: 'final',
  reply_to_id: null,
  client_message_id: null,
  created_at: '2026-09-26T00:00:00Z',
});
const history = (): SupervisorHistory => ({
  conversationId: 'conversation',
  authorityId: 'local',
  principalId: 'owner',
  cursor: 2,
  messages: [message('first', 1)],
  runs: [],
});
const event = (seq: number, type = 'message.final'): SupervisorEvent => ({
  conversation_id: 'conversation',
  seq,
  event_id: `event-${seq}`,
  type,
  schema_version: 1,
  entity_id: 'second',
  revision: 1,
  occurred_at: '2026-09-26T00:00:00Z',
  payload: message('second', 3),
});

test('reconnect duplicates and overlapping pages do not duplicate a reply', () => {
  const first = applySupervisorEvent(history(), event(3));
  assert.equal(first.messages.length, 2);
  assert.equal(applySupervisorEvent(first, event(3)), first);
  assert.equal(
    mergeMessages(first.messages, [message('second', 3), message('first', 1)])
      .length,
    2
  );
});
test('older responses cannot overwrite a newer revision', () => {
  const current = { ...message('first', 1, 2), body: 'Corrected response' };
  assert.equal(
    mergeMessages([current], [message('first', 1)])[0].body,
    current.body
  );
});
test('gaps and foreign authority events force resynchronisation', () => {
  assert.throws(() => applySupervisorEvent(history(), event(4)), /gap/);
  assert.throws(
    () =>
      applySupervisorEvent(history(), {
        ...event(3),
        conversation_id: 'foreign',
      }),
    /authority/
  );
});
test('history deletion clears already displayed private text', () => {
  const cleared = applySupervisorEvent(history(), event(3, 'history.cleared'));
  assert.equal(cleared.messages.length, 0);
  assert.equal(cleared.cursor, 3);
});
test('unrendered activity still advances the durable cursor', () => {
  const before = history();
  const next = applySupervisorEvent(before, event(3, 'action.status'));
  assert.equal(next.messages, before.messages);
  assert.equal(next.cursor, 3);
  assert.equal(next.messages.length, 1);
});

test('failed replies survive replay and late status pages cannot restore running state', () => {
  const run = {
    id: 'run',
    input_message_id: 'first',
    status: 'failed',
    generation: 2,
    error: 'model_authentication_failed',
  };
  const updated = applySupervisorEvent(history(), {
    ...event(3, 'run.status'),
    payload: run,
  });
  assert.deepEqual(updated.runs, [run]);
  assert.equal(
    mergeRuns(updated.runs, [
      { ...run, status: 'running', generation: 1, error: null },
    ])[0].status,
    'failed'
  );
  assert.deepEqual(
    applySupervisorEvent(updated, event(4, 'history.cleared')).runs,
    []
  );
});

test('run status is validated and retained only for the displayed history window', () => {
  assert.throws(
    () =>
      applySupervisorEvent(history(), {
        ...event(3, 'run.status'),
        payload: { status: 'failed' },
      }),
    /Invalid reply status/
  );
  const run = {
    id: 'run',
    input_message_id: 'first',
    status: 'pending',
    generation: 0,
    error: null,
  };
  const updated = applySupervisorEvent(history(), {
    ...event(3, 'run.status'),
    payload: run,
  });
  const later = {
    ...updated,
    messages: Array.from({ length: 200 }, (_, i) =>
      message(`later-${i}`, i + 4)
    ),
  };
  assert.equal(
    applySupervisorEvent(later, event(4, 'action.status')).runs.length,
    0
  );
});

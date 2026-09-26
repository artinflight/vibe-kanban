import assert from 'node:assert/strict';
import { test } from 'node:test';
import { applySupervisorEvent, mergeMessages } from './supervisor-state.ts';
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

import type {
  ConversationMessage,
  SupervisorEvent,
  SupervisorRunStatus,
} from 'shared/types';

export interface SupervisorHistory {
  conversationId: string;
  authorityId: string;
  principalId: string;
  cursor: number;
  messages: ConversationMessage[];
  runs: SupervisorRunStatus[];
}

export function mergeRuns(
  current: SupervisorRunStatus[],
  incoming: SupervisorRunStatus[]
) {
  const byId = new Map(current.map((run) => [run.id, run]));
  for (const run of incoming) {
    const before = byId.get(run.id);
    if (!before || run.generation >= before.generation) byId.set(run.id, run);
  }
  return [...byId.values()];
}

export function mergeMessages(
  current: ConversationMessage[],
  incoming: ConversationMessage[]
) {
  const byId = new Map(current.map((message) => [message.id, message]));
  for (const message of incoming) {
    const previous = byId.get(message.id);
    if (!previous || message.revision >= previous.revision)
      byId.set(message.id, message);
  }
  return [...byId.values()].sort((a, b) => a.created_seq - b.created_seq);
}

export function applySupervisorEvent(
  history: SupervisorHistory,
  event: SupervisorEvent
): SupervisorHistory {
  if (event.conversation_id !== history.conversationId)
    throw new Error('Conversation authority changed');
  if (event.seq <= history.cursor) return history;
  if (event.seq !== history.cursor + 1)
    throw new Error('Conversation replay gap');
  let messages = history.messages;
  let runs = history.runs;
  if (event.type === 'history.cleared') {
    messages = [];
    runs = [];
  }
  if (event.type === 'run.status') {
    const run = event.payload as SupervisorRunStatus;
    if (
      !run ||
      typeof run.id !== 'string' ||
      typeof run.input_message_id !== 'string' ||
      typeof run.status !== 'string' ||
      !Number.isSafeInteger(run.generation)
    )
      throw new Error('Invalid reply status');
    runs = mergeRuns(runs, [run]);
  }
  if (event.type === 'message.created' || event.type === 'message.final') {
    const message = event.payload as ConversationMessage;
    if (
      !message ||
      message.conversation_id !== history.conversationId ||
      typeof message.body !== 'string' ||
      typeof message.id !== 'string' ||
      !Number.isSafeInteger(message.created_seq) ||
      !Number.isSafeInteger(message.revision)
    )
      throw new Error('Invalid conversation message');
    messages = mergeMessages(messages, [message]);
  }
  // Status follows the retained message window, avoiding an ever-growing map.
  const retainedIds = new Set(
    messages.slice(-200).map((message) => message.id)
  );
  return {
    ...history,
    cursor: event.seq,
    messages,
    runs: runs.filter((run) => retainedIds.has(run.input_message_id)),
  };
}

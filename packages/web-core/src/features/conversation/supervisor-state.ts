import type { ConversationMessage, SupervisorEvent } from 'shared/types';

export interface SupervisorHistory {
  conversationId: string;
  authorityId: string;
  principalId: string;
  cursor: number;
  messages: ConversationMessage[];
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
  if (event.type === 'history.cleared') messages = [];
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
  return { ...history, cursor: event.seq, messages };
}

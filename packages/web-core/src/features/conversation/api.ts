import type {
  AcceptConversationMessage,
  ConversationAction,
  ConversationEvidence,
  ConversationMemory,
  ConversationMessage,
  MessageEvidenceRef,
  SupervisorCapabilities,
  SupervisorMessageReceipt,
  SupervisorSnapshot,
} from 'shared/types';
import { handleApiResponse } from '@/shared/lib/api';
import {
  makeLocalApiRequest,
  openLocalApiWebSocket,
} from '@/shared/lib/localApiTransport';

// The local supervisor belongs to this installation, regardless of the project
// or remote host currently selected in workspace navigation.
async function request<T>(
  path: string,
  method = 'GET',
  body?: unknown
): Promise<T> {
  const response = await makeLocalApiRequest(`/api/conversations${path}`, {
    hostScope: 'none',
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });
  return handleApiResponse<T>(response);
}

export const supervisorApi = {
  capabilities: () => request<SupervisorCapabilities>('/capabilities'),
  resolve: () => request<SupervisorSnapshot>('/resolve', 'POST'),
  snapshot: (id: string) => request<SupervisorSnapshot>(`/${id}`),
  messages: (id: string, before?: number) =>
    request<ConversationMessage[]>(
      `/${id}/messages?limit=50${before === undefined ? '' : `&before_seq=${before}`}`
    ),
  send: (id: string, input: AcceptConversationMessage) =>
    request<SupervisorMessageReceipt>(`/${id}/messages`, 'POST', input),
  actions: (id: string) => request<ConversationAction[]>(`/${id}/actions`),
  memories: (id: string) => request<ConversationMemory[]>(`/${id}/memories`),
  references: (id: string, message: string) =>
    request<MessageEvidenceRef[]>(`/${id}/messages/${message}/evidence`),
  evidence: (id: string, evidence: string) =>
    request<ConversationEvidence>(`/${id}/evidence/${evidence}`),
  forget: (id: string, memory: ConversationMemory) =>
    request<void>(`/${id}/memories/${memory.id}`, 'DELETE', {
      expected_revision: memory.revision,
    }),
  clear: (id: string, revision: number) =>
    request<SupervisorSnapshot>(`/${id}/history`, 'DELETE', {
      expected_revision: revision,
    }),
  export: (id: string) => request<unknown>(`/${id}/export`),
  connect: (id: string, cursor: number) =>
    openLocalApiWebSocket(
      `/api/conversations/${id}/events/ws?after_seq=${cursor}`,
      { hostScope: 'none' }
    ),
};

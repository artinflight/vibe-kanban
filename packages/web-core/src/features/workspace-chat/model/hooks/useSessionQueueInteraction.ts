import { useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { queueApi } from '@/shared/lib/api';
import type { ExecutorConfig, QueueStatus } from 'shared/types';

interface UseSessionQueueInteractionOptions {
  /** Session ID for queue operations */
  sessionId: string | undefined;
}

interface UseSessionQueueInteractionResult {
  /** Whether a message is currently queued */
  isQueued: boolean;
  /** The queued message content, if any */
  queuedMessage: string | null;
  /** The executor config from the queued message, if any */
  queuedConfig: ExecutorConfig | null;
  /** Number of queued follow-up messages */
  queuedCount: number;
  /** Whether a queue operation is in progress */
  isQueueLoading: boolean;
  /** Send a follow-up to the active agent, or queue it when active injection is unavailable */
  sendFollowUp: (
    message: string,
    executorConfig: ExecutorConfig
  ) => Promise<void>;
  /** Cancel the queued message */
  cancelQueue: () => Promise<void>;
  /** Refresh queue status from server */
  refreshQueueStatus: () => Promise<void>;
}

export const QUEUE_STATUS_KEY = 'queue-status';
const QUEUED_STATUS_REFRESH_MS = 3000;

/**
 * Hook to manage follow-up interaction for session messages.
 * The server injects into active Codex sessions when possible and otherwise
 * falls back to a queued follow-up.
 * Uses TanStack Query for caching and mutation handling.
 */
export function useSessionQueueInteraction({
  sessionId,
}: UseSessionQueueInteractionOptions): UseSessionQueueInteractionResult {
  const queryClient = useQueryClient();

  // Query for queue status
  const { data: queueStatus = { status: 'empty' as const }, refetch } =
    useQuery<QueueStatus>({
      queryKey: [QUEUE_STATUS_KEY, sessionId],
      queryFn: () => queueApi.getStatus(sessionId!),
      enabled: !!sessionId,
      refetchInterval: (query) =>
        query.state.data?.status === 'queued'
          ? QUEUED_STATUS_REFRESH_MS
          : false,
      refetchOnWindowFocus: true,
    });

  const isQueued = queueStatus.status === 'queued';
  const queuedMessageData = isQueued
    ? (queueStatus as Extract<QueueStatus, { status: 'queued' }>).message
    : null;
  const queuedMessage = queuedMessageData?.data.message ?? null;
  const queuedConfig: ExecutorConfig | null =
    queuedMessageData?.data.executor_config ?? null;
  const queuedCount = queuedMessageData?.messages.length ?? 0;

  // Mutation for sending or queueing a follow-up message
  const followUpMutation = useMutation({
    mutationFn: ({
      message,
      executorConfig,
    }: {
      message: string;
      executorConfig: ExecutorConfig;
    }) =>
      queueApi.queue(sessionId!, {
        message,
        executor_config: executorConfig,
      }),
    onSuccess: (status) => {
      queryClient.setQueryData([QUEUE_STATUS_KEY, sessionId], status);
    },
  });

  // Mutation for cancelling the queue
  const cancelMutation = useMutation({
    mutationFn: () => queueApi.cancel(sessionId!),
    onSuccess: (status) => {
      queryClient.setQueryData([QUEUE_STATUS_KEY, sessionId], status);
    },
  });

  const sendFollowUp = useCallback(
    async (message: string, executorConfig: ExecutorConfig) => {
      if (!sessionId) return;
      await followUpMutation.mutateAsync({
        message,
        executorConfig,
      });
    },
    [sessionId, followUpMutation]
  );

  const cancelQueue = useCallback(async () => {
    if (!sessionId) return;
    await cancelMutation.mutateAsync();
  }, [sessionId, cancelMutation]);

  const refreshQueueStatus = useCallback(async () => {
    if (!sessionId) return;
    await refetch();
  }, [sessionId, refetch]);

  return {
    isQueued,
    queuedMessage,
    queuedConfig,
    queuedCount,
    isQueueLoading: followUpMutation.isPending || cancelMutation.isPending,
    sendFollowUp,
    cancelQueue,
    refreshQueueStatus,
  };
}

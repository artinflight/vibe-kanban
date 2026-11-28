import { useQuery } from '@tanstack/react-query';
import type { NormalizedEntry } from 'shared/types';
import { handleApiResponse } from '@/shared/lib/api';
import { makeLocalApiRequest } from '@/shared/lib/localApiTransport';
import { isCapturedGitNotice } from '../gitPreservationNotice';

type CaptureStatus = {
  checkpoints: { execution_process_id: string; observation_state: string }[];
};

export function useQuietGitPreservationNotice(
  entry: NormalizedEntry | null,
  workspaceId: string | undefined,
  executionId: string
) {
  const notice = isCapturedGitNotice(entry, workspaceId, executionId);
  const status = useQuery({
    queryKey: ['gitPreservationCapture', workspaceId],
    queryFn: async ({ signal }) =>
      handleApiResponse<CaptureStatus>(
        await makeLocalApiRequest(
          `/api/workspaces/${workspaceId}/github-sync`,
          { signal }
        )
      ),
    enabled: notice,
    staleTime: 5_000,
    refetchInterval: notice ? 5_000 : false,
    retry: false,
  });
  // Keep current failures, publication errors and unknown/unavailable status visible.
  return (
    notice &&
    status.isSuccess &&
    Array.isArray(status.data?.checkpoints) &&
    status.data.checkpoints.some(
      (checkpoint) =>
        checkpoint.execution_process_id === executionId &&
        checkpoint.observation_state === 'observed'
    )
  );
}

import { useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { workspacesApi } from '@/shared/lib/api';
import { workspaceSummaryKeys } from '@/shared/hooks/workspaceSummaryKeys';

/** Workspace-wide read: call only from an explicit user action. */
export function useWorkspaceSeenAction() {
  const queryClient = useQueryClient();
  return useCallback(
    async (workspaceId: string) => {
      await workspacesApi.markSeen(workspaceId);
      void queryClient.invalidateQueries({
        queryKey: workspaceSummaryKeys.all,
      });
    },
    [queryClient]
  );
}

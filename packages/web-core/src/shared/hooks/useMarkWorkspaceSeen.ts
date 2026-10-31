import { useCallback, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { workspacesApi } from '@/shared/lib/api';
import { workspaceSummaryKeys } from '@/shared/hooks/workspaceSummaryKeys';

/** Explicit read action shared by chat visibility and deliberate reselection. */
export function useWorkspaceSeenAction() {
  const queryClient = useQueryClient();
  return useCallback(
    (workspaceId: string) => {
      if (document.visibilityState !== 'visible') return;
      void workspacesApi
        .markSeen(workspaceId)
        .then(() => {
          void queryClient.invalidateQueries({
            queryKey: workspaceSummaryKeys.all,
          });
        })
        .catch((error) => {
          console.warn('Failed to mark workspace as seen:', error);
        });
    },
    [queryClient]
  );
}

/** Pass an ID only while that workspace's loaded conversation is displayed. */
export function useMarkWorkspaceSeen(visibleWorkspaceId: string | undefined) {
  const markWorkspaceSeen = useWorkspaceSeenAction();
  useEffect(() => {
    if (!visibleWorkspaceId) return;
    const markVisibleChatSeen = () => markWorkspaceSeen(visibleWorkspaceId);
    // Clear on opening/returning to chat, never on a polled completion update.
    markVisibleChatSeen();
    document.addEventListener('visibilitychange', markVisibleChatSeen);
    return () => {
      document.removeEventListener('visibilitychange', markVisibleChatSeen);
    };
  }, [visibleWorkspaceId, markWorkspaceSeen]);
}

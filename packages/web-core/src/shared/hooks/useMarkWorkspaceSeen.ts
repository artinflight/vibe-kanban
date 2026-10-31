import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { workspacesApi } from '@/shared/lib/api';
import { workspaceSummaryKeys } from '@/shared/hooks/workspaceSummaryKeys';

/** Pass an ID only while that workspace's loaded conversation is displayed. */
export function useMarkWorkspaceSeen(visibleWorkspaceId: string | undefined) {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!visibleWorkspaceId) return;

    const markVisibleChatSeen = () => {
      if (document.visibilityState !== 'visible') return;
      void workspacesApi
        .markSeen(visibleWorkspaceId)
        .then(() => {
          void queryClient.invalidateQueries({
            queryKey: workspaceSummaryKeys.all,
          });
        })
        .catch((error) => {
          console.warn('Failed to mark workspace as seen:', error);
        });
    };

    // Clear on opening/returning to chat, never on a polled completion update.
    markVisibleChatSeen();
    document.addEventListener('visibilitychange', markVisibleChatSeen);
    return () => {
      document.removeEventListener('visibilitychange', markVisibleChatSeen);
    };
  }, [visibleWorkspaceId, queryClient]);
}

import { useCallback } from 'react';
import { useAppNavigation } from '@/shared/hooks/useAppNavigation';
import { useCurrentKanbanRouteState } from '@/shared/hooks/useCurrentKanbanRouteState';
import { useWorkspaceSeenAction } from '@/shared/hooks/useMarkWorkspaceSeen';

/** Same-route navigation does not remount chat or rerun its visibility effect. */
export function useOpenProjectWorkspace() {
  const navigation = useAppNavigation();
  const route = useCurrentKanbanRouteState();
  const markWorkspaceSeen = useWorkspaceSeenAction();
  return useCallback(
    (projectId: string, issueId: string, workspaceId: string) => {
      if (
        route.projectId === projectId &&
        route.issueId === issueId &&
        route.workspaceId === workspaceId &&
        !route.isCreateMode
      ) {
        markWorkspaceSeen(workspaceId);
      }
      navigation.goToProjectIssueWorkspace(projectId, issueId, workspaceId);
    },
    [
      navigation,
      route.projectId,
      route.issueId,
      route.workspaceId,
      route.isCreateMode,
      markWorkspaceSeen,
    ]
  );
}

import { useCallback } from 'react';
import { useAppNavigation } from '@/shared/hooks/useAppNavigation';
import { requestWorkspaceRead } from '@/shared/lib/workspaceReadIntent';

/** The loaded, displayed transcript gates acknowledgements after selection. */
export function useOpenProjectWorkspace() {
  const navigation = useAppNavigation();
  return useCallback(
    (projectId: string, issueId: string, workspaceId: string) => {
      navigation.goToProjectIssueWorkspace(projectId, issueId, workspaceId);
      requestWorkspaceRead(workspaceId);
    },
    [navigation]
  );
}

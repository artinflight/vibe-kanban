import { useCallback } from 'react';
import { useAppNavigation } from '@/shared/hooks/useAppNavigation';

/** Navigation never acknowledges replies, including same-route reselection. */
export function useOpenProjectWorkspace() {
  const navigation = useAppNavigation();
  return useCallback(
    (projectId: string, issueId: string, workspaceId: string) => {
      navigation.goToProjectIssueWorkspace(projectId, issueId, workspaceId);
    },
    [navigation]
  );
}

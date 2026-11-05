import { useMutation, useQueryClient } from '@tanstack/react-query';
import { workspacesApi } from '@/shared/lib/api';
import type { CreateAndStartWorkspaceRequest } from 'shared/types';
import { workspaceSummaryKeys } from '@/shared/hooks/workspaceSummaryKeys';
import { dispatchWorkspaceLinkRefresh } from '@/shared/lib/workspaceLinkRefresh';
import { useLocalParticipants } from '@/shared/hooks/useLocalParticipants';
import { createLinkedWorkspace } from '@/shared/lib/createLinkedWorkspace';
interface CreateWorkspaceParams {
  data: CreateAndStartWorkspaceRequest;
  linkToIssue?: {
    remoteProjectId: string;
    issueId: string;
  };
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  const { isLocalOnlySession } = useLocalParticipants();

  const refreshIssueWorkspaceState = (projectId?: string | null) => {
    void queryClient.invalidateQueries({ queryKey: workspaceSummaryKeys.all });
    void queryClient.invalidateQueries({ queryKey: ['taskWorkspaces'] });
    void queryClient.invalidateQueries({
      queryKey: ['taskWorkspacesWithSessions'],
    });
    void queryClient.invalidateQueries({ queryKey: ['workspaceSessions'] });
    void queryClient.invalidateQueries({
      queryKey: ['workspaceCreateDefaults'],
    });

    if (!projectId) {
      return;
    }

    // The local issue/workspace shapes can lag the create/link transaction by a
    // tick, so re-fire the refresh signal after the mutation settles.
    dispatchWorkspaceLinkRefresh({ projectId });
    window.setTimeout(() => {
      dispatchWorkspaceLinkRefresh({ projectId });
    }, 250);
    window.setTimeout(() => {
      dispatchWorkspaceLinkRefresh({ projectId });
    }, 1000);
  };

  const createWorkspace = useMutation({
    retry: false,
    mutationFn: async ({ data, linkToIssue }: CreateWorkspaceParams) =>
      createLinkedWorkspace(
        workspacesApi,
        data,
        linkToIssue,
        isLocalOnlySession,
        async (project) => {
          const response = await fetch(
            `/v1/fallback/issues?project_id=${encodeURIComponent(project)}`
          );
          if (!response.ok)
            throw new Error('Unable to verify the selected issue.');
          return response.json();
        }
      ),
    onSuccess: (_data, variables) => {
      refreshIssueWorkspaceState(
        variables.linkToIssue?.remoteProjectId ??
          variables.data.linked_issue?.remote_project_id
      );
    },
    onError: (err) => {
      console.error('Failed to create workspace:', err);
    },
  });

  return { createWorkspace };
}

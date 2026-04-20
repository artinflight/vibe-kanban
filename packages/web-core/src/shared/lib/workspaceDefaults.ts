import { workspacesApi, repoApi } from '@/shared/lib/api';
import type { Workspace } from 'shared/remote-types';
import { getValidProjectRepoDefaults } from '@/shared/hooks/useProjectRepoDefaults';

export interface WorkspaceDefaults {
  preferredRepos: Array<{ repo_id: string; target_branch: string | null }>;
}

function getMostRecentLocalWorkspace(
  remoteWorkspaces: Workspace[],
  localWorkspaceIds: Set<string>,
  predicate: (workspace: Workspace) => boolean
): Workspace | null {
  return (
    remoteWorkspaces
      .filter(
        (workspace) =>
          predicate(workspace) &&
          workspace.local_workspace_id !== null &&
          localWorkspaceIds.has(workspace.local_workspace_id)
      )
      .sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )[0] ?? null
  );
}

async function getWorkspaceRepoDefaults(
  localWorkspaceId: string
): Promise<WorkspaceDefaults> {
  const repos = await workspacesApi.getRepos(localWorkspaceId);

  return {
    preferredRepos: repos.map((repo) => ({
      repo_id: repo.id,
      target_branch: repo.target_branch,
    })),
  };
}

/**
 * Fetches workspace creation defaults using a project-aware priority chain:
 * 1. Most recent workspace linked to the same issue (if issueId provided)
 * 2. Scratch project-repo defaults (if projectId provided and valid repos exist)
 * 3. Most recent workspace for the same project (if projectId provided)
 * 4. Globally most recent workspace
 * 5. null (no defaults)
 */
export async function getWorkspaceDefaults(
  remoteWorkspaces: Workspace[],
  localWorkspaceIds: Set<string>,
  projectId?: string | null,
  issueId?: string | null
): Promise<WorkspaceDefaults | null> {
  // Priority 1: Most recent workspace linked to the same issue
  if (issueId) {
    const issueRecent = getMostRecentLocalWorkspace(
      remoteWorkspaces,
      localWorkspaceIds,
      (workspace) => workspace.issue_id === issueId
    );

    if (issueRecent?.local_workspace_id) {
      try {
        return await getWorkspaceRepoDefaults(issueRecent.local_workspace_id);
      } catch (err) {
        console.warn('Failed to fetch issue workspace defaults:', err);
      }
    }
  }

  // Priority 2: Scratch project-repo defaults
  if (projectId) {
    try {
      const allRepos = await repoApi.list();
      const availableRepoIds = new Set(allRepos.map((r) => r.id));
      const scratchDefaults = await getValidProjectRepoDefaults(
        projectId,
        availableRepoIds
      );
      if (scratchDefaults.length > 0) {
        return {
          preferredRepos: scratchDefaults.map((r) => ({
            repo_id: r.repo_id,
            target_branch: r.target_branch,
          })),
        };
      }
    } catch (err) {
      console.warn('Failed to fetch project scratch defaults:', err);
    }

    // Priority 3: Most recent workspace for the same project
    const projectRecent = getMostRecentLocalWorkspace(
      remoteWorkspaces,
      localWorkspaceIds,
      (workspace) => workspace.project_id === projectId
    );

    if (projectRecent?.local_workspace_id) {
      try {
        return await getWorkspaceRepoDefaults(projectRecent.local_workspace_id);
      } catch (err) {
        console.warn('Failed to fetch project workspace defaults:', err);
      }
    }
  }

  // Priority 4: Globally most recent workspace
  const mostRecent = getMostRecentLocalWorkspace(
    remoteWorkspaces,
    localWorkspaceIds,
    () => true
  );

  if (!mostRecent?.local_workspace_id) {
    return null;
  }

  try {
    return await getWorkspaceRepoDefaults(mostRecent.local_workspace_id);
  } catch (err) {
    console.warn('Failed to fetch workspace defaults:', err);
    return null;
  }
}

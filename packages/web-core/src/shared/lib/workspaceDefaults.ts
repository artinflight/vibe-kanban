import { workspacesApi, repoApi, projectsApi } from '@/shared/lib/api';
import type { Workspace } from 'shared/remote-types';
import { getValidProjectRepoDefaults } from '@/shared/hooks/useProjectRepoDefaults';
import type { RepoWithTargetBranch } from 'shared/types';

export interface WorkspaceDefaults {
  preferredRepos: Array<{ repo_id: string; target_branch: string | null }>;
}

function normalizeDefaultKey(value: string | null | undefined): string {
  return (value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');
}

function pathBasename(path: string | null | undefined): string {
  if (!path) return '';
  return path.split(/[\\/]/).filter(Boolean).pop() ?? '';
}

function toPreferredRepos(repos: RepoWithTargetBranch[]): WorkspaceDefaults {
  return {
    preferredRepos: repos.map((repo) => ({
      repo_id: repo.id,
      target_branch: repo.target_branch || repo.default_target_branch || 'main',
    })),
  };
}

async function getProjectRepoAssociationDefaults(
  projectId: string
): Promise<WorkspaceDefaults | null> {
  try {
    const repos = await projectsApi.listRepos(projectId);
    if (repos.length > 0) {
      return toPreferredRepos(repos);
    }
  } catch (err) {
    console.warn('Failed to fetch project repo associations:', err);
  }

  try {
    const [project, repos] = await Promise.all([
      projectsApi.getById(projectId),
      repoApi.list(),
    ]);
    const projectKey = normalizeDefaultKey(project.name);
    const defaultWorkingDirKey = normalizeDefaultKey(
      project.default_agent_working_dir
    );

    const matchingRepos = repos.filter((repo) => {
      if (
        defaultWorkingDirKey &&
        normalizeDefaultKey(repo.default_working_dir) === defaultWorkingDirKey
      ) {
        return true;
      }

      return [repo.display_name, repo.name, pathBasename(repo.path)].some(
        (value) => normalizeDefaultKey(value) === projectKey
      );
    });

    if (matchingRepos.length === 1) {
      const repo = matchingRepos[0];
      if (!repo) {
        return null;
      }
      return toPreferredRepos([
        {
          ...repo,
          target_branch: repo.default_target_branch || 'main',
        },
      ]);
    }
  } catch (err) {
    console.warn('Failed to infer project repo default:', err);
  }

  return null;
}

/**
 * Fetches workspace creation defaults using a project-aware priority chain:
 * 1. Scratch project-repo defaults (if projectId provided and valid repos exist)
 * 2. Project repo association or exact project/repo name match
 * 3. Most recent workspace for the same project (if projectId provided)
 * 4. Globally most recent workspace when no project is known
 * 5. null (no defaults)
 */
export async function getWorkspaceDefaults(
  remoteWorkspaces: Workspace[],
  localWorkspaceIds: Set<string>,
  projectId?: string | null
): Promise<WorkspaceDefaults | null> {
  // Priority 1: Scratch project-repo defaults
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

    // Priority 2: Project repo association, with a refresh-only fallback for live
    // frontends when the backend route has not been restarted yet.
    const projectRepoDefaults =
      await getProjectRepoAssociationDefaults(projectId);
    if (projectRepoDefaults) {
      return projectRepoDefaults;
    }

    // Priority 3: Most recent workspace for the same project
    const projectRecent = remoteWorkspaces
      .filter(
        (w) =>
          w.project_id === projectId &&
          w.local_workspace_id !== null &&
          localWorkspaceIds.has(w.local_workspace_id)
      )
      .sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      )[0];

    if (projectRecent?.local_workspace_id) {
      try {
        const [repos] = await Promise.all([
          workspacesApi.getRepos(projectRecent.local_workspace_id),
          workspacesApi.get(projectRecent.local_workspace_id),
        ]);
        return {
          preferredRepos: repos.map((r) => ({
            repo_id: r.id,
            target_branch: r.target_branch,
          })),
        };
      } catch (err) {
        console.warn('Failed to fetch project workspace defaults:', err);
      }
    }

    return null;
  }

  // Priority 4: Globally most recent workspace only for unscoped workspace creation.
  const mostRecent = remoteWorkspaces
    .filter(
      (w) =>
        w.local_workspace_id !== null &&
        localWorkspaceIds.has(w.local_workspace_id)
    )
    .sort(
      (a, b) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    )[0];

  if (!mostRecent?.local_workspace_id) {
    return null;
  }

  try {
    const [repos] = await Promise.all([
      workspacesApi.getRepos(mostRecent.local_workspace_id),
      workspacesApi.get(mostRecent.local_workspace_id),
    ]);

    return {
      preferredRepos: repos.map((r) => ({
        repo_id: r.id,
        target_branch: r.target_branch,
      })),
    };
  } catch (err) {
    console.warn('Failed to fetch workspace defaults:', err);
    return null;
  }
}

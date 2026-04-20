import { beforeEach, describe, expect, it, vi } from 'vitest';
import { getWorkspaceDefaults } from './workspaceDefaults';
import { repoApi, workspacesApi } from '@/shared/lib/api';
import { getValidProjectRepoDefaults } from '@/shared/hooks/useProjectRepoDefaults';
import type { Workspace } from 'shared/remote-types';

vi.mock('@/shared/lib/api', () => ({
  repoApi: {
    list: vi.fn(),
  },
  workspacesApi: {
    getRepos: vi.fn(),
  },
}));

vi.mock('@/shared/hooks/useProjectRepoDefaults', () => ({
  getValidProjectRepoDefaults: vi.fn(),
}));

const mockedRepoApiList = vi.mocked(repoApi.list);
const mockedGetWorkspaceRepos = vi.mocked(workspacesApi.getRepos);
const mockedGetValidProjectRepoDefaults = vi.mocked(
  getValidProjectRepoDefaults
);

function createWorkspace(overrides: Partial<Workspace> = {}): Workspace {
  return {
    id: 'remote-workspace-id',
    local_workspace_id: 'local-workspace-id',
    issue_id: null,
    project_id: 'project-1',
    owner_user_id: 'user-1',
    name: 'Workspace',
    archived: false,
    created_at: '2026-04-18T00:00:00Z',
    updated_at: '2026-04-18T00:00:00Z',
    files_changed: 0,
    lines_added: 0,
    lines_removed: 0,
    ...overrides,
  };
}

describe('getWorkspaceDefaults', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedRepoApiList.mockResolvedValue([]);
    mockedGetWorkspaceRepos.mockResolvedValue([]);
    mockedGetValidProjectRepoDefaults.mockResolvedValue([]);
  });

  it('prefers the latest local workspace linked to the same issue', async () => {
    mockedGetWorkspaceRepos.mockResolvedValue([
      { id: 'repo-issue', target_branch: 'issue-branch' } as never,
    ]);

    const defaults = await getWorkspaceDefaults(
      [
        createWorkspace({
          issue_id: 'issue-1',
          project_id: 'project-1',
          local_workspace_id: 'local-older',
          updated_at: '2026-04-17T00:00:00Z',
        }),
        createWorkspace({
          issue_id: 'issue-1',
          project_id: 'project-1',
          local_workspace_id: 'local-newer',
          updated_at: '2026-04-19T00:00:00Z',
        }),
        createWorkspace({
          issue_id: 'issue-2',
          project_id: 'project-1',
          local_workspace_id: 'local-other',
          updated_at: '2026-04-20T00:00:00Z',
        }),
      ],
      new Set(['local-older', 'local-newer', 'local-other']),
      'project-1',
      'issue-1'
    );

    expect(mockedGetWorkspaceRepos).toHaveBeenCalledWith('local-newer');
    expect(defaults).toEqual({
      preferredRepos: [
        { repo_id: 'repo-issue', target_branch: 'issue-branch' },
      ],
    });
    expect(mockedGetValidProjectRepoDefaults).not.toHaveBeenCalled();
  });

  it('falls back to project repo defaults when no same-issue workspace exists', async () => {
    mockedRepoApiList.mockResolvedValue([{ id: 'repo-project' }] as never);
    mockedGetValidProjectRepoDefaults.mockResolvedValue([
      { repo_id: 'repo-project', target_branch: 'staging' } as never,
    ]);

    const defaults = await getWorkspaceDefaults(
      [
        createWorkspace({
          issue_id: 'other-issue',
          project_id: 'project-1',
          local_workspace_id: 'local-other',
        }),
      ],
      new Set(['local-other']),
      'project-1',
      'issue-1'
    );

    expect(defaults).toEqual({
      preferredRepos: [{ repo_id: 'repo-project', target_branch: 'staging' }],
    });
    expect(mockedGetWorkspaceRepos).not.toHaveBeenCalled();
  });
});

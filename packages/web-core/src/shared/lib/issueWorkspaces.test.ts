import { describe, expect, it } from 'vitest';
import { buildIssueWorkspaceStats } from './issueWorkspaces';
import type { SidebarWorkspace } from '@/shared/hooks/useWorkspaces';

function createLocalWorkspace(
  overrides: Partial<SidebarWorkspace> = {}
): SidebarWorkspace {
  return {
    id: 'local-1',
    taskId: null,
    name: 'Workspace One',
    branch: 'workspace/one',
    createdAt: '2026-04-19T00:00:00.000Z',
    updatedAt: '2026-04-19T00:00:00.000Z',
    description: '',
    ...overrides,
  };
}

describe('buildIssueWorkspaceStats', () => {
  it('includes locally linked workspaces when the remote issue feed is stale', () => {
    const localWorkspace = createLocalWorkspace({
      id: 'local-1',
      taskId: 'issue-1',
      isRunning: true,
    });

    const result = buildIssueWorkspaceStats({
      issueId: 'issue-1',
      remoteWorkspaces: [],
      localWorkspacesById: new Map([[localWorkspace.id, localWorkspace]]),
      allLocalWorkspaces: [localWorkspace],
      membersWithProfilesById: new Map(),
      userId: 'user-1',
    });

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      id: 'local:local-1',
      localWorkspaceId: 'local-1',
      name: 'Workspace One',
      isRunning: true,
    });
  });

  it('does not duplicate a workspace already present in the remote issue feed', () => {
    const localWorkspace = createLocalWorkspace({
      id: 'local-1',
      taskId: 'issue-1',
    });

    const result = buildIssueWorkspaceStats({
      issueId: 'issue-1',
      remoteWorkspaces: [
        {
          id: 'remote-1',
          local_workspace_id: 'local-1',
          owner_user_id: 'user-1',
          name: 'Workspace One',
          archived: false,
          files_changed: 3,
          lines_added: 10,
          lines_removed: 2,
          updated_at: '2026-04-19T00:05:00.000Z',
        },
      ],
      localWorkspacesById: new Map([[localWorkspace.id, localWorkspace]]),
      allLocalWorkspaces: [localWorkspace],
      membersWithProfilesById: new Map(),
      userId: 'user-1',
    });

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      id: 'remote-1',
      localWorkspaceId: 'local-1',
      filesChanged: 3,
    });
  });

  it('resolves a local workspace by name when the remote link is missing the local id', () => {
    const localWorkspace = createLocalWorkspace({
      id: 'local-1',
      name: 'Workspace One',
      taskId: null,
    });

    const result = buildIssueWorkspaceStats({
      issueId: 'issue-1',
      remoteWorkspaces: [
        {
          id: 'remote-1',
          local_workspace_id: null,
          owner_user_id: 'user-2',
          name: 'workspace one',
          archived: false,
          files_changed: null,
          lines_added: null,
          lines_removed: null,
          updated_at: '2026-04-19T00:05:00.000Z',
        },
      ],
      localWorkspacesById: new Map([[localWorkspace.id, localWorkspace]]),
      allLocalWorkspaces: [localWorkspace],
      membersWithProfilesById: new Map(),
      userId: 'user-1',
    });

    expect(result).toHaveLength(1);
    expect(result[0].localWorkspaceId).toBe('local-1');
  });
});

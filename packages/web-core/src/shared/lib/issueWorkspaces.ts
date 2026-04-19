import type { SidebarWorkspace } from '@/shared/hooks/useWorkspaces';
import type { OrganizationMemberWithProfile } from 'shared/types';
import type {
  WorkspacePr,
  WorkspaceWithStats,
} from '@vibe/ui/components/IssueWorkspaceCard';

type RemoteIssueWorkspace = {
  id: string;
  local_workspace_id: string | null;
  owner_user_id: string;
  name: string | null;
  archived: boolean;
  files_changed: number | null;
  lines_added: number | null;
  lines_removed: number | null;
  updated_at: string;
};

export function resolveLocalWorkspaceId(
  remoteWorkspace: Pick<RemoteIssueWorkspace, 'local_workspace_id' | 'name'>,
  localWorkspacesById: Map<string, SidebarWorkspace>,
  localWorkspaces: SidebarWorkspace[]
): string | null {
  if (
    remoteWorkspace.local_workspace_id &&
    localWorkspacesById.has(remoteWorkspace.local_workspace_id)
  ) {
    return remoteWorkspace.local_workspace_id;
  }

  const normalizedName = remoteWorkspace.name?.trim().toLowerCase() ?? '';
  if (!normalizedName) {
    return null;
  }

  const matches = localWorkspaces.filter(
    (workspace) => workspace.name.trim().toLowerCase() === normalizedName
  );

  return matches.length === 1 ? matches[0].id : null;
}

export function buildIssueWorkspaceStats(args: {
  issueId: string;
  remoteWorkspaces: RemoteIssueWorkspace[];
  localWorkspacesById: Map<string, SidebarWorkspace>;
  allLocalWorkspaces: SidebarWorkspace[];
  prsByWorkspaceId?: Map<string, WorkspacePr[]>;
  membersWithProfilesById: Map<string, OrganizationMemberWithProfile>;
  userId?: string | null;
}): WorkspaceWithStats[] {
  const {
    issueId,
    remoteWorkspaces,
    localWorkspacesById,
    allLocalWorkspaces,
    prsByWorkspaceId,
    membersWithProfilesById,
    userId,
  } = args;

  const workspaces: WorkspaceWithStats[] = [];
  const includedLocalWorkspaceIds = new Set<string>();

  for (const workspace of remoteWorkspaces) {
    const resolvedLocalWorkspaceId = resolveLocalWorkspaceId(
      workspace,
      localWorkspacesById,
      allLocalWorkspaces
    );
    const localWorkspace = resolvedLocalWorkspaceId
      ? localWorkspacesById.get(resolvedLocalWorkspaceId)
      : undefined;

    if (resolvedLocalWorkspaceId) {
      includedLocalWorkspaceIds.add(resolvedLocalWorkspaceId);
    }

    workspaces.push({
      id: workspace.id,
      localWorkspaceId: resolvedLocalWorkspaceId,
      name: workspace.name,
      archived: workspace.archived,
      filesChanged:
        workspace.files_changed ?? localWorkspace?.filesChanged ?? 0,
      linesAdded: workspace.lines_added ?? localWorkspace?.linesAdded ?? 0,
      linesRemoved:
        workspace.lines_removed ?? localWorkspace?.linesRemoved ?? 0,
      prs: prsByWorkspaceId?.get(workspace.id) ?? [],
      owner: membersWithProfilesById.get(workspace.owner_user_id) ?? null,
      updatedAt: workspace.updated_at,
      isOwnedByCurrentUser: workspace.owner_user_id === userId,
      isRunning: localWorkspace?.isRunning,
      hasPendingApproval: localWorkspace?.hasPendingApproval,
      hasRunningDevServer: localWorkspace?.hasRunningDevServer,
      hasUnseenActivity: localWorkspace?.hasUnseenActivity,
      latestProcessCompletedAt: localWorkspace?.latestProcessCompletedAt,
      latestProcessStatus: localWorkspace?.latestProcessStatus,
    });
  }

  for (const localWorkspace of allLocalWorkspaces) {
    if (localWorkspace.taskId !== issueId) {
      continue;
    }

    if (includedLocalWorkspaceIds.has(localWorkspace.id)) {
      continue;
    }

    workspaces.push({
      id: `local:${localWorkspace.id}`,
      localWorkspaceId: localWorkspace.id,
      name: localWorkspace.name,
      archived: localWorkspace.isArchived ?? false,
      filesChanged: localWorkspace.filesChanged ?? 0,
      linesAdded: localWorkspace.linesAdded ?? 0,
      linesRemoved: localWorkspace.linesRemoved ?? 0,
      prs: [],
      owner: null,
      updatedAt: localWorkspace.updatedAt,
      isOwnedByCurrentUser: true,
      isRunning: localWorkspace.isRunning,
      hasPendingApproval: localWorkspace.hasPendingApproval,
      hasRunningDevServer: localWorkspace.hasRunningDevServer,
      hasUnseenActivity: localWorkspace.hasUnseenActivity,
      latestProcessCompletedAt: localWorkspace.latestProcessCompletedAt,
      latestProcessStatus: localWorkspace.latestProcessStatus,
    });
  }

  return workspaces.sort(
    (left, right) =>
      new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
  );
}

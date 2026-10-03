interface WorkspaceActivity {
  isRunning?: boolean;
  hasPendingApproval?: boolean;
  hasUnseenActivity?: boolean;
  activeSubagentCount?: number;
  unresolvedSubagentCount?: number;
}

export function paginateWorkspaceSidebar<T extends WorkspaceActivity>(
  workspaces: T[],
  limit: number,
  searching: boolean,
  accordion: boolean
): T[] {
  if (searching) return workspaces;

  // Idle history is paginated; actionable work must remain visible in its section.
  return workspaces.filter(
    (workspace, index) =>
      index < limit ||
      (accordion &&
        (workspace.isRunning ||
          workspace.hasPendingApproval ||
          workspace.hasUnseenActivity ||
          (workspace.activeSubagentCount ?? 0) > 0 ||
          (workspace.unresolvedSubagentCount ?? 0) > 0))
  );
}

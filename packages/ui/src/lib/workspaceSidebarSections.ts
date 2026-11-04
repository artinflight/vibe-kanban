export interface SidebarActivity {
  isRunning?: boolean;
  hasPendingApproval?: boolean;
  hasUnseenActivity?: boolean;
  dotUnreadCount?: number;
  dotNeedsAttentionCount?: number;
  activeSubagentCount?: number;
  unresolvedSubagentCount?: number;
  readLater?: boolean;
}

export const hasUnreadSidebarActivity = (workspace: SidebarActivity) =>
  !!workspace.hasUnseenActivity || (workspace.dotUnreadCount ?? 0) > 0;

export function workspaceSidebarSections<T extends SidebarActivity>(
  collection: T[]
) {
  const isActive = (ws: T) =>
    !!ws.isRunning ||
    (ws.activeSubagentCount ?? 0) + (ws.unresolvedSubagentCount ?? 0) > 0;
  const isDeferred = (ws: T) => !!ws.readLater && hasUnreadSidebarActivity(ws);
  const needsAttention = (ws: T) =>
    (ws.dotNeedsAttentionCount ?? 0) > 0 ||
    ws.hasPendingApproval ||
    (!isActive(ws) && hasUnreadSidebarActivity(ws));
  return {
    raisedHandWorkspaces: collection.filter(
      (ws) => !isDeferred(ws) && needsAttention(ws)
    ),
    readLaterWorkspaces: collection.filter(isDeferred),
    runningWorkspaces: collection.filter(
      (ws) => !isDeferred(ws) && isActive(ws)
    ),
    idleWorkspaces: collection.filter(
      (ws) => !isDeferred(ws) && !isActive(ws) && !needsAttention(ws)
    ),
  };
}

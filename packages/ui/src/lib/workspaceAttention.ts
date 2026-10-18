export interface WorkspaceReviewState {
  hasPendingApproval?: boolean | null;
  hasUnseenActivity?: boolean | null;
  isRunning?: boolean | null;
  latestProcessStatus?: string | null;
}

export function getWorkspaceAttentionLabel(
  workspace: WorkspaceReviewState
): 'Needs approval' | 'Needs review' | undefined {
  if (
    workspace.latestProcessStatus === 'failed' ||
    workspace.latestProcessStatus === 'killed'
  )
    return undefined;
  if (workspace.hasPendingApproval) return 'Needs approval';
  if (
    workspace.hasUnseenActivity &&
    !workspace.isRunning &&
    workspace.latestProcessStatus !== 'running'
  )
    return 'Needs review';
  return undefined;
}

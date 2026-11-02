export const WORKSPACE_READ_INTENT = 'vk-workspace-read-intent';

/** Deliberate selection; the displayed transcript decides whether it was read. */
export function requestWorkspaceRead(workspaceId: string) {
  window.dispatchEvent(
    new CustomEvent(WORKSPACE_READ_INTENT, { detail: { workspaceId } })
  );
}

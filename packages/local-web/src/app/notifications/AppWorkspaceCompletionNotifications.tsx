import { useEffect, useRef } from 'react';
import { useUserSystem } from '@/shared/hooks/useUserSystem';
import {
  type SidebarWorkspace,
  useWorkspaces,
} from '@/shared/hooks/useWorkspaces';
import {
  browserNotificationPermission,
  showBrowserNotification,
} from '@/shared/lib/browserNotifications';

type WorkspaceNotificationSnapshot = {
  isRunning: boolean;
  latestProcessCompletedAt?: string;
  latestProcessStatus?: SidebarWorkspace['latestProcessStatus'];
};

function notificationTitle(workspace: SidebarWorkspace): string {
  if (workspace.latestProcessStatus === 'failed') {
    return `VK turn failed: ${workspace.name}`;
  }

  return `VK turn complete: ${workspace.name}`;
}

function notificationBody(workspace: SidebarWorkspace): string {
  const status =
    workspace.latestProcessStatus === 'failed' ? 'Failed' : 'Completed';

  return `Workspace: ${workspace.name}\nBranch: ${workspace.branch}\nStatus: ${status}`;
}

function toSnapshot(
  workspace: SidebarWorkspace
): WorkspaceNotificationSnapshot {
  return {
    isRunning: workspace.isRunning ?? false,
    latestProcessCompletedAt: workspace.latestProcessCompletedAt,
    latestProcessStatus: workspace.latestProcessStatus,
  };
}

export function AppWorkspaceCompletionNotifications() {
  const { config } = useUserSystem();
  const { workspaces } = useWorkspaces();
  const previousByWorkspaceIdRef = useRef<
    Map<string, WorkspaceNotificationSnapshot>
  >(new Map());
  const initializedRef = useRef(false);

  useEffect(() => {
    const nextByWorkspaceId = new Map(
      workspaces.map((workspace) => [workspace.id, toSnapshot(workspace)])
    );

    if (!initializedRef.current) {
      previousByWorkspaceIdRef.current = nextByWorkspaceId;
      initializedRef.current = true;
      return;
    }

    const pushEnabled = config?.notifications.push_enabled ?? false;
    if (!pushEnabled || browserNotificationPermission() !== 'granted') {
      previousByWorkspaceIdRef.current = nextByWorkspaceId;
      return;
    }

    for (const workspace of workspaces) {
      const previous = previousByWorkspaceIdRef.current.get(workspace.id);
      if (!previous?.isRunning || workspace.isRunning) {
        continue;
      }

      const completedAtChanged =
        workspace.latestProcessCompletedAt &&
        workspace.latestProcessCompletedAt !==
          previous.latestProcessCompletedAt;
      const completedOrFailed =
        workspace.latestProcessStatus === 'completed' ||
        workspace.latestProcessStatus === 'failed';

      if (!completedAtChanged || !completedOrFailed) {
        continue;
      }

      showBrowserNotification({
        title: notificationTitle(workspace),
        body: notificationBody(workspace),
        tag: `vk-workspace-${workspace.id}`,
      });
    }

    previousByWorkspaceIdRef.current = nextByWorkspaceId;
  }, [config?.notifications.push_enabled, workspaces]);

  return null;
}

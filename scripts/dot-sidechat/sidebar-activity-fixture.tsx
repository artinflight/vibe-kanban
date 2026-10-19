import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import {
  WorkspacesSidebar,
  type WorkspacesSidebarWorkspace,
} from '../../packages/ui/src/components/WorkspacesSidebar';
import { workspaceDotNotification } from '../../packages/web-core/src/shared/lib/dotWorkspaceActivity';

const issue = {
  project_id: 'p',
  issue_id: 'i',
  unread_count: 1,
  needs_attention_count: 0,
  shared_unread_count: 0,
  shared_needs_attention_count: 0,
};
const dispatch = { ...issue, workspace_id: 'target' };
const rows: WorkspacesSidebarWorkspace[] = [
  {
    id: 'running-unread',
    name: 'Running unread',
    dotManaged: true,
    isRunning: true,
    hasUnseenActivity: true,
    dotUnreadCount: 5,
  },
  {
    id: 'running-attention',
    name: 'Running attention',
    isRunning: true,
    dotNeedsAttentionCount: 1,
  },
  {
    id: 'running-approval',
    name: 'Running approval',
    isRunning: true,
    hasPendingApproval: true,
  },
  {
    id: 'active-subagent',
    name: 'Active subagent',
    activeSubagentCount: 1,
    hasUnseenActivity: true,
    dotUnreadCount: 1,
  },
  {
    id: 'unresolved-subagent',
    name: 'Unresolved subagent',
    unresolvedSubagentCount: 1,
    dotUnreadCount: 1,
  },
  {
    id: 'subagent-approval',
    name: 'Subagent approval',
    activeSubagentCount: 1,
    hasPendingApproval: true,
  },
  {
    id: 'subagent-attention',
    name: 'Subagent attention',
    unresolvedSubagentCount: 1,
    dotNeedsAttentionCount: 1,
  },
  { id: 'idle-unseen', name: 'Idle unseen', hasUnseenActivity: true },
  { id: 'idle-dot', name: 'Idle Dot unread', dotUnreadCount: 1 },
  { id: 'idle-approval', name: 'Idle approval', hasPendingApproval: true },
  { id: 'idle-attention', name: 'Idle attention', dotNeedsAttentionCount: 1 },
  { id: 'idle', name: 'Idle clean', dotManaged: true },
  ...['target', 'sibling'].map((id) => {
    const activity = workspaceDotNotification(
      'i',
      issue,
      id === 'target' ? dispatch : undefined
    );
    return {
      id,
      name: id === 'target' ? 'Dispatch target' : 'Dispatch sibling',
      dotUnreadCount: activity?.unread_count,
      dotNeedsAttentionCount: activity?.needs_attention_count,
    };
  }),
];
function Fixture() {
  const [workspaces, setWorkspaces] = useState(rows);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(
    null
  );
  // Tests change inputs through normal React rendering, without touching any API.
  Object.assign(window, {
    fixtureSelect: setSelectedWorkspaceId,
    fixtureReverse: () => setWorkspaces((previous) => [...previous].reverse()),
    fixtureUpdate: (id: string, changes: Partial<WorkspacesSidebarWorkspace>) =>
      setWorkspaces((previous) =>
        previous.map((ws) => (ws.id === id ? { ...ws, ...changes } : ws))
      ),
  });
  return (
    <WorkspacesSidebar
      workspaces={workspaces}
      activityWorkspaces={workspaces}
      totalWorkspacesCount={workspaces.length}
      selectedWorkspaceId={selectedWorkspaceId}
      onSelectWorkspace={(id) => {
        Object.assign(window, { fixtureLastSelected: id });
        setSelectedWorkspaceId(id);
      }}
      searchQuery=""
      onSearchChange={() => {}}
      layoutMode="accordion"
    />
  );
}
createRoot(document.getElementById('root')!).render(<Fixture />);

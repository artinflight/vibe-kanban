import { createRoot } from 'react-dom/client';
import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DotSidechatLive } from '../../packages/web-core/src/pages/workspaces/DotSidechatLive';
import { WorkspaceSummary } from '../../packages/ui/src/components/WorkspaceSummary';
import { IssueWorkspaceCard } from '../../packages/ui/src/components/IssueWorkspaceCard';
import { useDotNotifications } from '../../packages/web-core/src/shared/hooks/useDotNotifications';

function Fixture() {
  const [visible, setVisible] = useState(false);
  const [workspace, setWorkspace] = useState(
    '11111111-1111-4111-8111-111111111111'
  );
  const notifications = useDotNotifications();
  const state = notifications.find((n) => n.issue_id === 'issue-fixture');
  const dot = {
    dotUnreadCount: state?.unread_count ?? 0,
    dotNeedsAttentionCount: state?.needs_attention_count ?? 0,
  };
  return (
    <div className="new-design">
      <aside id="workspace-list">
        <WorkspaceSummary
          name="Workspace A"
          hasUnseenActivity
          latestProcessStatus="completed"
          {...dot}
        />
        <WorkspaceSummary
          name="Workspace B"
          hasPendingApproval
          isRunning
          {...dot}
        />
        <IssueWorkspaceCard
          workspace={{
            id: 'fixture-card',
            localWorkspaceId: null,
            name: 'Issue workspace',
            archived: false,
            filesChanged: 0,
            linesAdded: 0,
            linesRemoved: 0,
            prs: [],
            owner: null,
            updatedAt: '2026-10-16T00:00:00Z',
            isOwnedByCurrentUser: true,
            hasUnseenActivity: true,
            ...dot,
          }}
        />
        <span id="coding-unread">Coding-agent unread remains</span>
      </aside>
      <button id="toggle-dot" onClick={() => setVisible((v) => !v)}>
        Show or hide Dot
      </button>
      <button
        id="sibling"
        onClick={() => {
          setWorkspace('22222222-2222-4222-8222-222222222222');
          setVisible(true);
        }}
      >
        Open sibling conversation
      </button>
      <div
        id="dot-slot"
        style={{ display: visible ? 'flex' : 'none', height: 440 }}
      >
        <DotSidechatLive key={workspace} workspaceId={workspace} />
      </div>
    </div>
  );
}
createRoot(document.getElementById('root')!).render(
  <QueryClientProvider
    client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
  >
    <Fixture />
  </QueryClientProvider>
);

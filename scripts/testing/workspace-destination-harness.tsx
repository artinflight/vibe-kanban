import React from 'react';
import { createRoot } from 'react-dom/client';
import { Navbar } from '../../packages/ui/src/components/Navbar';
import { useWorkspaceRecord } from '../../packages/web-core/src/shared/hooks/useWorkspaceRecord';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectRightSidebarContainer } from '../../packages/web-core/src/pages/kanban/ProjectRightSidebarContainer';
import { IssueWorkspacesSectionContainer } from '../../packages/web-core/src/pages/kanban/IssueWorkspacesSectionContainer';
import { useWorkspaceSessions } from '../../packages/web-core/src/shared/hooks/useWorkspaceSessions';
import { useKanbanFilters } from '../../packages/web-core/src/features/kanban/model/hooks/useKanbanFilters';
import {
  resolveKanbanProjectState,
  resolveKanbanViewFilters,
} from '../../packages/web-core/src/shared/stores/useUiPreferencesStore';
const f = (window as any).fixture;
const client = new QueryClient({
  defaultOptions: {
    queries: { retry: false, gcTime: Infinity },
    mutations: { retry: false },
  },
});
function Probe() {
  const { data: workspace } = useWorkspaceRecord(f.workspaceId);
  f.selection = useWorkspaceSessions(f.workspaceId);
  f.renders.push({
    workspace: f.workspaceId,
    session: f.selection.selectedSessionId,
    isNew: f.selection.isNewSessionMode,
  });
  const defaultFilters = resolveKanbanProjectState({
    activeViewId: f.view ?? 'personal',
  } as any).filters;
  const filters = resolveKanbanViewFilters(
    f.view ?? 'personal',
    f.filters ?? defaultFilters
  );
  f.filtersApplied = filters;
  f.visibleIssues = useKanbanFilters({
    ...f.filterParams,
    filters,
    currentUserId: f.user ?? 'self',
  }).filteredIssues;
  return f.showNavbar ? (
    <div
      style={{
        display: f.mobile ? 'flex' : 'grid',
        flexDirection: 'column',
        gridTemplateColumns: '64px 1fr',
        minWidth: 0,
        width: '100%',
      }}
    >
      {!f.mobile && <div />}
      <Navbar
        workspaceTitle={workspace?.name || workspace?.branch}
        mobileMode={f.mobile}
      />
    </div>
  ) : null;
}
const root = createRoot(document.getElementById('root')!);
f.render = () =>
  root.render(
    <QueryClientProvider client={client}>
      <div
        className="new-design"
        style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}
      >
        <Probe />
        <ProjectRightSidebarContainer
          expectedIssueId={null}
          onExpectIssueOpen={() => {}}
        />
        <IssueWorkspacesSectionContainer issueId="issue" />
      </div>
    </QueryClientProvider>
  );
f.setSessions = (id: string, sessions: any[]) =>
  client.setQueryData(['workspaceSessions', f.host ?? 'local', id], sessions);
f.refresh = () => client.invalidateQueries();
f.close = () => {
  root.unmount();
  client.clear();
};
f.render();

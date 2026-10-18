import { useState, useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectCollaborationLayout } from '../../packages/web-core/src/pages/kanban/ProjectCollaborationLayout';
import { WorkspacesSidebar } from '../../packages/ui/src/components/WorkspacesSidebar';
import { useDotProjectNotifications } from '../../packages/web-core/src/shared/hooks/useDotNotifications';
import {
  projectDotNotices,
  openProjectDotChat,
} from '../../packages/web-core/src/shared/lib/dotProjectNotices';
const ids = {
  project: '11111111-1111-4111-8111-111111111111',
  issue: '22222222-2222-4222-8222-222222222222',
  a: '33333333-3333-4333-8333-333333333333',
  b: '44444444-4444-4444-8444-444444444444',
};
const other = '55555555-5555-4555-8555-555555555555';
const subscribe = (fn: () => void) => {
  window.addEventListener('popstate', fn);
  return () => window.removeEventListener('popstate', fn);
};
const notify = () => window.dispatchEvent(new PopStateEvent('popstate'));
function navigate(projectId: string, destination: 'project' | 'a' = 'project') {
  history.pushState(
    { projectId, destination },
    '',
    '/projects/' +
      projectId +
      (destination === 'a'
        ? '/issues/' + ids.issue + '/workspaces/' + ids.a
        : '')
  );
  notify();
}
Object.assign(window, {
  fixtureHistory: {
    get location() {
      return { href: location.pathname, state: history.state ?? {} };
    },
    subscribe,
    push(path: string, state: unknown) {
      history.pushState(state, '', path);
      notify();
    },
    back() {
      history.back();
    },
  },
  fixtureRoute: navigate,
});
const projects = [
  { id: ids.project, name: 'Synthetic project Alpha' },
  { id: other, name: 'Synthetic project Beta' },
];
const rows = [
  { id: ids.a, name: 'Workspace target', dotUnreadCount: 1 },
  { id: ids.b, name: 'Workspace sibling' },
];
function Fixture() {
  useSyncExternalStore(
    subscribe,
    () => location.pathname + JSON.stringify(history.state)
  );
  const [mode, setMode] = useState<'accordion' | 'flat'>('accordion');
  const [empty, setEmpty] = useState(false);
  const [view, setView] = useState('workspaces');
  const data = useDotProjectNotifications();
  const notices = projectDotNotices(data, projects);
  const projectId = history.state?.projectId ?? ids.project;
  const destination = history.state?.destination ?? 'project';
  Object.assign(window, {
    fixtureSetMode: setMode,
    fixtureSetEmpty: setEmpty,
    fixtureShowWorkspaces: () => {
      history.replaceState(
        { ...history.state, mobileSheet: undefined },
        '',
        location.pathname
      );
      notify();
      setView('workspaces');
    },
  });
  return (
    <div className="new-design fixture-notices" data-view={view}>
      <div id="fixture-controls">
        <button
          id="route-workspace"
          onClick={() => {
            navigate(ids.project, 'a');
            setView('chat');
          }}
        >
          Open workspace
        </button>
        <button
          id="route-project"
          onClick={() => {
            navigate(ids.project);
            setView('chat');
          }}
        >
          Open project
        </button>
        <button
          id="show-workspaces"
          onClick={() => window.fixtureShowWorkspaces()}
        >
          Workspaces
        </button>
      </div>
      <div className="fixture-body">
        <div data-workspace-pane>
          <WorkspacesSidebar
            workspaces={empty ? [] : rows}
            activityWorkspaces={empty ? [] : rows}
            totalWorkspacesCount={empty ? 0 : 2}
            selectedWorkspaceId={ids.a}
            onSelectWorkspace={(id) => {
              window.fixtureWorkspaceSelections.push(id);
              navigate(ids.project, 'a');
            }}
            searchQuery=""
            onSearchChange={() => {}}
            layoutMode={mode}
            projectDotNotices={notices}
            onOpenProjectChat={(id) => {
              setView('chat');
              openProjectDotChat(
                id,
                (project) => navigate(project),
                destination === 'project' ? projectId : null
              );
            }}
          />
        </div>
        <ProjectCollaborationLayout
          projectId={projectId}
          projectName={
            projects.find((p) => p.id === projectId)?.name ?? projectId
          }
          workspaceId={destination === 'a' ? ids.a : null}
          issueId={destination === 'a' ? ids.issue : null}
        >
          <main id="displayed-workspace">
            {destination === 'a' ? 'Workspace a' : 'Project ' + projectId}
          </main>
        </ProjectCollaborationLayout>
      </div>
    </div>
  );
}
Object.assign(window, { fixtureWorkspaceSelections: [] });
const client = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});
createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={client}>
    <Fixture />
  </QueryClientProvider>
);

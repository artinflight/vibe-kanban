import { useSyncExternalStore } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProjectCollaborationLayout } from '../../packages/web-core/src/pages/kanban/ProjectCollaborationLayout';
const ids = {
  project: '11111111-1111-4111-8111-111111111111',
  issue: '22222222-2222-4222-8222-222222222222',
  a: '33333333-3333-4333-8333-333333333333',
  b: '44444444-4444-4444-8444-444444444444',
};
const subscribe = (fn: () => void) => {
  window.addEventListener('popstate', fn);
  return () => window.removeEventListener('popstate', fn);
};
const notify = () => window.dispatchEvent(new PopStateEvent('popstate'));
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
  fixtureNavigate: (destination: 'project' | 'a' | 'b') => {
    const path =
      '/projects/' +
      ids.project +
      (destination === 'project'
        ? ''
        : '/issues/' + ids.issue + '/workspaces/' + ids[destination]);
    history.pushState({ destination }, '', path);
    notify();
  },
});
function Fixture() {
  useSyncExternalStore(
    subscribe,
    () => location.pathname + JSON.stringify(history.state)
  );
  const destination = (history.state?.destination ?? 'project') as
    | 'project'
    | 'a'
    | 'b';
  return (
    <QueryClientProvider client={client}>
      <div className="new-design fixture-project">
        <div id="fixture-controls">
          {(['project', 'a', 'b'] as const).map((d) => (
            <button
              key={d}
              id={'route-' + d}
              onClick={() => window.fixtureNavigate(d)}
            >
              {d === 'project' ? 'Close workspace' : 'Open workspace ' + d}
            </button>
          ))}
          <button id="route-back" onClick={() => history.back()}>
            Back
          </button>
        </div>
        <ProjectCollaborationLayout
          projectId={ids.project}
          projectName="Synthetic project"
          workspaceId={destination === 'project' ? null : ids[destination]}
          issueId={destination === 'project' ? null : ids.issue}
        >
          <main id="displayed-workspace">
            {destination === 'project'
              ? 'Project board'
              : 'Displayed workspace ' + destination}
          </main>
        </ProjectCollaborationLayout>
      </div>
    </QueryClientProvider>
  );
}
const client = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});
createRoot(document.getElementById('root')!).render(<Fixture />);

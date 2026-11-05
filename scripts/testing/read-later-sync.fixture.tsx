import { createRoot } from 'react-dom/client';
import i18next from 'i18next';
import { I18nextProvider } from 'react-i18next';
import common from '../../packages/web-core/src/i18n/locales/en/common.json';
import { WorkspacesSidebar } from '../../packages/ui/src/components/WorkspacesSidebar';
import { useReadLater } from '../../packages/web-core/src/shared/hooks/useReadLater';

function Fixture() {
  const { isReadLater, setReadLater, syncError } = useReadLater();
  const item = {
    kind: 'workspace' as const,
    id: 'premiere',
    name: 'Premiere Pro to mobile',
  };
  return (
    <WorkspacesSidebar
      workspaces={[
        {
          id: item.id,
          name: item.name,
          hasUnseenActivity: true,
          readLater: isReadLater(item.kind, item.id),
        },
      ]}
      totalWorkspacesCount={1}
      selectedWorkspaceId={null}
      onSelectWorkspace={() => {}}
      searchQuery=""
      onSearchChange={() => {}}
      readLaterSyncError={!!syncError}
      onToggleWorkspaceReadLater={() =>
        setReadLater(item, !isReadLater(item.kind, item.id))
      }
      onOpenWorkspaceActions={() => {}}
    />
  );
}
void i18next.init({ lng: 'en', resources: { en: { common } } }).then(() => {
  createRoot(document.getElementById('root')!).render(
    <I18nextProvider i18n={i18next}>
      <Fixture />
    </I18nextProvider>
  );
});

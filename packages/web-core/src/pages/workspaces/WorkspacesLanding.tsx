import { useEffect } from 'react';
import { useMobileActiveTab } from '@/shared/stores/useUiPreferencesStore';
import { usePageTitle } from '@/shared/hooks/usePageTitle';
import { WorkspacesSidebarContainer } from './WorkspacesSidebarContainer';

export function WorkspacesLanding() {
  const [, setMobileTab] = useMobileActiveTab();
  usePageTitle('Workspaces');
  useEffect(() => {
    setMobileTab('workspaces');
  }, [setMobileTab]);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col bg-primary">
      <WorkspacesSidebarContainer />
    </div>
  );
}

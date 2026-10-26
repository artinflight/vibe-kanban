// Synthetic transport/provider boundary for the actual project panel and hooks.
import React, { useState } from 'react';
import { useSessionSend } from '../../packages/web-core/src/features/workspace-chat/model/hooks/useSessionSend';
export const fixture = () => (window as any).fixture;
export const useHostId = () => fixture().host ?? null;
export const getHostRequestScopeQueryKey = (id: string | null) => id ?? 'local';
export const useAppRuntime = () => 'local';
export class ApiError extends Error {}
export const savedChatMessagesApi = {};
export const workspacesApi = {
  get: (id: string) => fixture().getWorkspace(id),
};
export const sessionsApi = {
  getByWorkspace: (id: string) => fixture().getSessions(id),
  create: (value: unknown) => fixture().createSession(value),
  followUp: (id: string, value: unknown) => fixture().followUp(id, value),
};
export const useWorkspaceContext = () => fixture().local;
export const useUserContext = () => ({ workspaces: fixture().remote });
export const useProjectContext = () => ({
  projectId: 'project',
  getIssue: (id: string) => ({ id, simple_id: 'T1' }),
  getWorkspacesForIssue: () => fixture().remote,
  pullRequests: [],
  issues: [],
  issuesById: new Map(),
});
export const useCurrentKanbanRouteState = () => ({
  issueId: 'issue',
  workspaceId: fixture().workspaceId,
});
export const useAppNavigation = () =>
  new Proxy(
    {},
    {
      get:
        (_target, name) =>
        (...args: unknown[]) =>
          fixture().navigations.push([name, ...args]),
    }
  );
export const useParams = () => ({ projectId: 'project' });
export const useOrgContext = () => ({ membersWithProfilesById: new Map() });
export const useAuth = () => ({ userId: 'self' });
export const useTranslation = () => ({ t: (key: string) => key });
export const useProjectWorkspaceCreateDraft = () => ({});
export const dispatchWorkspaceLinkRefresh = () => {};
export const getWorkspaceDefaults = () => ({});
export const buildLinkedIssueCreateState = () => ({});
export const buildLocalWorkspaceIdSet = () => new Set();
export const buildWorkspaceCreateInitialState = () => ({});
export const buildWorkspaceCreatePrompt = () => '';
export const useKanbanIssueComposer = () => null;
export const buildKanbanIssueComposerKey = () => 'fixture';
export const closeKanbanIssueComposer = () => {};
export const usePinConversationToBottomOnChatBoxResize = () => {};
export const QUEUE_STATUS_KEY = 'queue';
export const Pass = ({ children }: any) => children;
export const Tooltip = Pass;
export const MobileDrawer = () => null;
export const SyncErrorIndicator = () => null;
export const ExecutionProcessesProvider = Pass;
export const ApprovalFeedbackProvider = Pass;
export const EntriesProvider = Pass;
export const MessageEditProvider = Pass;
export const CreateModeProvider = Pass;
export const RetryUiProvider = Pass;
export const CreateChatBoxContainer = () => null;
export const KanbanIssuePanelContainer = () => null;
export const ConfirmDialog = { show: async () => {} };
export const DeleteWorkspaceDialog = ConfirmDialog;
export const RenameWorkspaceDialog = ConfirmDialog;
export const ConversationList = React.forwardRef((props: any, _ref) => (
  <output
    data-history-workspace={props.attempt.id}
    data-history-session={props.sessionScopeId}
  />
));
export const IssueWorkspacesSection = (props: any) => {
  fixture().cards = props;
  return <output id="cards" />;
};
// Use the production send hook. Only the transport and visual shell are mocked.
export function SessionChatBoxContainer(props: any) {
  const [draft, setDraft] = useState('');
  const workspaceId = props.session?.workspace_id ?? props.workspaceId;
  const sender = useSessionSend({
    workspaceId,
    sessionId: props.session?.id,
    isNewSessionMode: props.mode === 'new-session',
    onSelectSession: props.onSelectSession,
    executorConfig: { executor: 'CODEX', variant: 'fixture' } as any,
  });
  fixture().composer = { ...props, sender };
  return (
    <div
      id="composer"
      data-mode={props.mode}
      data-workspace={workspaceId}
      data-session={props.session?.id}
    >
      <input value={draft} onChange={(e) => setDraft(e.target.value)} />
      <button
        disabled={props.mode === 'placeholder'}
        onClick={() => void sender.send(draft)}
      >
        Synthetic send
      </button>
    </div>
  );
}

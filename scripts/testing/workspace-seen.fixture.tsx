import { forwardRef, type ReactNode } from "react";

export const state = {
  workspaceId: "a" as string | null,
  workspace: { id: "a" } as { id: string } | undefined,
  loading: false,
  createIssue: false,
  createWorkspace: false,
  calls: [] as string[],
  fail: false,
};
export const workspacesApi = {
  markSeen: async (id: string) => {
    state.calls.push(id);
    if (state.fail) throw new Error("offline");
  },
};
export const workspaceSummaryKeys = { all: ["workspace-summaries"] };
export const useTranslation = () => ({ t: (key: string) => key });
export const useAppNavigation = () => ({ goToProject() {} });
export const useProjectContext = () => ({
  projectId: "p",
  getIssue: () => null,
  issuesById: new Map(),
  isLoading: false,
});
export const useUserContext = () => ({ workspaces: [] });
export const useWorkspaceContext = () => ({
  activeWorkspaces: [],
  archivedWorkspaces: [],
});
export const useCurrentKanbanRouteState = () => ({
  workspaceId: state.workspaceId,
  issueId: state.workspaceId ? "issue" : null,
  draftId: "draft",
  isWorkspaceCreateMode: state.createWorkspace,
});
export const useWorkspaceRecord = () => ({
  data: state.workspace,
  isLoading: state.loading,
});
export const useWorkspaceSessions = () => ({
  sessions: [],
  selectedSessionId: "session",
});
export const useKanbanIssueComposer = () => (state.createIssue ? {} : null);
export const buildKanbanIssueComposerKey = () => "key";
export const closeKanbanIssueComposer = () => {};
export const createWorkspaceWithSession = (workspace: unknown) => workspace;
export const usePinConversationToBottomOnChatBoxResize = () => {};
const Wrapper = ({ children }: { children?: ReactNode }) => <>{children}</>;
const Empty = forwardRef(() => null);
export {
  Wrapper as ExecutionProcessesProvider,
  Wrapper as ApprovalFeedbackProvider,
  Wrapper as EntriesProvider,
  Wrapper as MessageEditProvider,
  Wrapper as CreateModeProvider,
  Wrapper as RetryUiProvider,
  Empty as SessionChatBoxContainer,
  Empty as CreateChatBoxContainer,
  Empty as KanbanIssuePanelContainer,
  Empty as ConversationList,
  Empty as ArrowDownIcon,
  Empty as ArrowsOutIcon,
  Empty as XIcon,
};

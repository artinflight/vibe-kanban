export const state = {
  creates: 0,
  calls: [],
  failDot: true,
  navigations: [],
  editCalls: 0,
  issueId: null,
  wait: null,
  issueWait: null,
  workspaceWait: null,
  scratchWait: null,
  scratchRequests: [],
  scratchWrites: [],
  expected: [],
  runtime: 'local',
};
export const issue = {
  id: 'created',
  project_id: 'p',
  simple_id: 'T1',
  title: 'Dot task',
  description: null,
  status_id: 'todo',
  priority: null,
  sort_order: 0,
  hasUnseenActivity: true,
};
const statuses = [{ id: 'todo', name: 'To do', color: 'blue', sort_order: 0 }];
const issues = [issue];
const empty = [];
const project = {
  projectId: 'p',
  issues,
  statuses,
  tags: empty,
  issueAssignees: empty,
  issueTags: empty,
  isLoading: false,
  insertIssue: () => {
    state.creates++;
    return { persisted: state.issueWait ?? Promise.resolve(issue) };
  },
  insertIssueAssignee: ({ user_id, issue_id }) => ({
    persisted: (async () => {
      state.calls.push([issue_id, user_id]);
      if (user_id === 'seamus' && state.wait) await state.wait;
      if (user_id === 'dot' && state.failDot) throw new Error('POST failed');
    })(),
  }),
  insertIssueTag: () => {},
  removeIssueTag: () => {},
  insertTag: () => {},
  updateIssue: () => {},
  getTagsForIssue: () => empty,
  getPullRequestsForIssue: () => empty,
};
export const useProjectContext = () => project;
const members = new Map(
  ['dot', 'seamus'].map((user_id) => [
    user_id,
    {
      user_id,
      username: user_id,
      first_name: user_id,
      last_name: null,
      avatar_url: null,
    },
  ])
);
export const useOrgContext = () => ({
  isLoading: false,
  membersWithProfilesById: members,
});
const actions = {
  openStatusSelection: () => {},
  openPrioritySelection: () => {},
  openAssigneeSelection: () => {
    state.editCalls++;
  },
};
export const useActions = () => actions;
const user = { workspaces: empty };
export const useUserContext = () => user;
const workspace = { activeWorkspaces: empty, archivedWorkspaces: empty };
export const useWorkspaceContext = () => workspace;
const system = { sharedApiBase: null };
export const useUserSystem = () => system;
export const useCurrentKanbanRouteState = () => ({
  hostId: null,
  issueId: state.issueId,
});
const navigation = {
  goToProjectIssue: (p, id) => state.navigations.push(id),
  goToProject: () => state.navigations.push('closed'),
  goToProjectIssueWorkspaceCreate: (projectId, issueId, draftId) =>
    state.navigations.push(['workspace', projectId, issueId, draftId]),
  goToProjectWorkspaceCreate: (projectId, draftId) =>
    state.navigations.push(['workspace', projectId, draftId]),
};
export const useAppNavigation = () => navigation;
// Keep persistWorkspaceCreateDraft and its serializer real; delay only the API
// transport so navigation assertions exercise the actual post-write boundary.
export const scratchApi = {
  update: async (type, id, data) => {
    const request = { type, id, ...data };
    state.scratchRequests.push(request);
    if (state.scratchWait) await state.scratchWait;
    state.scratchWrites.push(request);
  },
};
export const localStorageScratchUpdate = () => true;
export const useAppRuntime = () => state.runtime;
const prefs = {
  createDraftWorkspaceByDefault: false,
  setCreateDraftWorkspaceByDefault: () => {},
};
export const useUiPreferencesStore = (sel) => sel(prefs);
const translate = (key, opts) => key + (opts ? JSON.stringify(opts) : '');
const translation = { t: translate };
export const useTranslation = () => translation;
const query = { invalidateQueries: async () => {} };
export const useQueryClient = () => query;
export const useDebouncedCallback = (fn) => ({
  debounced: fn,
  cancel: () => {},
});
const attachment = {
  uploadFiles: () => {},
  getAttachmentIds: () => empty,
  clearAttachments: () => {},
  isUploading: false,
  hasPendingAttachments: false,
  uploadError: null,
  clearUploadError: () => {},
  localAttachments: empty,
};
export const useAzureAttachments = () => attachment;
export const useDropzone = () => ({
  getRootProps: () => ({}),
  getInputProps: () => ({}),
  isDragActive: false,
  open: () => {},
});
export const commitIssueAttachments = async () => {};
export const deleteAttachment = async () => {};
export const extractAttachmentIds = () => new Set();
export const removeAttachmentMarkdownBySource = () => ({ removed: false });
export const replaceAttachmentSource = () => ({ replaced: false });
export const getWorkspaceDefaults = async () => {
  if (state.workspaceWait) await state.workspaceWait;
  return {};
};
export const CommandBarDialog = { show: async () => {} };
export const ConfirmDialog = CommandBarDialog;
export const AssigneeSelectionDialog = CommandBarDialog;
export const ProjectSelectionDialog = CommandBarDialog;
export const LinkPrToIssueDialog = CommandBarDialog;
export const IssueCommentsSectionContainer = () => null;
export const IssueSubIssuesSectionContainer = () => null;
export const IssueRelationshipsSectionContainer = () => null;
export const IssueWorkspacesSectionContainer = () => null;
export const SearchableTagDropdownContainer = () => null;
export default () => null;

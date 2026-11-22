export const state = {
  workspace: { id: 'workspace-id', task_id: 'inbox-issue', has_unseen_turns: true },
  links: [] as unknown[][],
};
export const workspacesApi = {
  async createAndStart() {
    return { workspace: state.workspace };
  },
  async linkToIssue(...args: unknown[]) {
    state.links.push(args);
  },
};
export const useMutation = (options: unknown) => options;
export const useQueryClient = () => ({ invalidateQueries: () => undefined });
export const workspaceSummaryKeys = { all: ['workspaces'] };
export const dispatchWorkspaceLinkRefresh = () => undefined;

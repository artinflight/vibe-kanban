import type {
  CreateAndStartWorkspaceRequest,
  CreateAndStartWorkspaceResponse,
  Workspace,
} from 'shared/types';

type IssueLink = { remoteProjectId: string; issueId: string };
type WorkspaceApi = {
  createAndStart: (
    data: CreateAndStartWorkspaceRequest
  ) => Promise<CreateAndStartWorkspaceResponse>;
  linkToIssue: (
    workspace: string,
    project: string,
    issue: string
  ) => Promise<void>;
  get: (workspace: string) => Promise<Workspace>;
};

export class WorkspaceLinkError extends Error {
  readonly workspaceId: string;

  constructor(workspaceId: string) {
    super(
      `Workspace ${workspaceId} was created, but its issue link could not be verified. Keep this workspace and repair its link; do not create a replacement.`
    );
    this.workspaceId = workspaceId;
  }
}

export async function createLinkedWorkspace(
  api: WorkspaceApi,
  data: CreateAndStartWorkspaceRequest,
  linkToIssue: IssueLink | undefined,
  localOnly: boolean,
  readIssues: (project: string) => Promise<unknown>
): Promise<{ workspace: Workspace }> {
  const linkedIssue =
    data.linked_issue ??
    (linkToIssue
      ? {
          remote_project_id: linkToIssue.remoteProjectId,
          issue_id: linkToIssue.issueId,
        }
      : null);
  if (
    linkedIssue &&
    linkToIssue &&
    (linkedIssue.issue_id !== linkToIssue.issueId ||
      linkedIssue.remote_project_id !== linkToIssue.remoteProjectId)
  ) {
    throw new Error('Issue selection changed. Select the issue again.');
  }
  if (localOnly) {
    if (!linkedIssue) {
      throw new Error('Select an issue before creating a workspace.');
    }
    const page = (await readIssues(linkedIssue.remote_project_id)) as {
      issues?: { id: string; project_id: string }[];
    } | null;
    if (
      !Array.isArray(page?.issues) ||
      page.issues.filter(
        (issue) =>
          issue.id === linkedIssue.issue_id &&
          issue.project_id === linkedIssue.remote_project_id
      ).length !== 1
    ) {
      throw new Error(
        'The selected issue could not be verified in this project.'
      );
    }
  }

  let { workspace } = await api.createAndStart({
    ...data,
    linked_issue: linkedIssue,
  });
  if (
    localOnly &&
    workspace.task_id &&
    workspace.task_id !== linkedIssue?.issue_id
  ) {
    throw new WorkspaceLinkError(workspace.id);
  }
  if (linkedIssue && !workspace.task_id) {
    try {
      await api.linkToIssue(
        workspace.id,
        linkedIssue.remote_project_id,
        linkedIssue.issue_id
      );
      if (localOnly) {
        workspace = await api.get(workspace.id);
        if (workspace.task_id !== linkedIssue.issue_id) {
          throw new WorkspaceLinkError(workspace.id);
        }
      }
    } catch {
      throw new WorkspaceLinkError(workspace.id);
    }
  }
  return { workspace };
}

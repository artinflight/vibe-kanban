export interface IssueCreationProgress<Issue, Form> {
  form: Form;
  issue: Issue | null;
  prepared: boolean;
  completedAssigneeIds: string[];
}

export class IssueAssignmentPersistenceError extends Error {
  readonly failedUserIds: string[];

  constructor(failedUserIds: string[]) {
    super('Some issue assignments could not be saved');
    this.failedUserIds = failedUserIds;
  }
}

/** Resume the same saved issue; never repeat confirmed assignment writes. */
export async function resumeIssueCreation<
  Issue,
  Form extends { assigneeIds: string[] },
>(
  initial: IssueCreationProgress<Issue, Form>,
  operations: {
    createIssue: (form: Form) => Promise<Issue>;
    prepareIssue: (issue: Issue, form: Form) => Promise<void>;
    insertAssignee: (issue: Issue, userId: string) => Promise<unknown>;
    checkpoint: (progress: IssueCreationProgress<Issue, Form>) => void;
  }
): Promise<Issue> {
  let progress = initial;
  const checkpoint = (patch: Partial<typeof progress>) => {
    progress = { ...progress, ...patch };
    operations.checkpoint(progress);
  };

  if (!progress.issue) {
    const issue = await operations.createIssue(progress.form);
    // Save identity before any later operation can fail or the panel remounts.
    checkpoint({ issue });
  }
  const issue = progress.issue!;
  if (!progress.prepared) {
    await operations.prepareIssue(issue, progress.form);
    checkpoint({ prepared: true });
  }

  const remaining = [...new Set(progress.form.assigneeIds)].filter(
    (id) => !progress.completedAssigneeIds.includes(id)
  );
  // Wait for every outcome, including when the first request rejects.
  const results = await Promise.allSettled(
    remaining.map(async (id) => {
      await operations.insertAssignee(issue, id);
      checkpoint({
        completedAssigneeIds: [...progress.completedAssigneeIds, id],
      });
    })
  );
  const failedUserIds = remaining.filter(
    (_, index) => results[index].status === 'rejected'
  );
  if (failedUserIds.length > 0) {
    throw new IssueAssignmentPersistenceError(failedUserIds);
  }
  return issue;
}

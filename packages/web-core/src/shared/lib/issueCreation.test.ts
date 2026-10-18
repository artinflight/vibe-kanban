import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  IssueAssignmentPersistenceError,
  resumeIssueCreation,
  type IssueCreationProgress,
} from './issueCreation.ts';

function fixture(assigneeIds = ['dot', 'seamus']) {
  const issue = { id: 'saved-issue', hasUnseenActivity: true };
  let progress: IssueCreationProgress<typeof issue, { assigneeIds: string[] }> =
    {
      form: { assigneeIds },
      issue: null,
      prepared: false,
      completedAssigneeIds: [],
    };
  let creates = 0;
  let prepares = 0;
  const assignmentCalls: string[] = [];
  const failures = new Set(['dot']);
  const operations = {
    createIssue: async () => {
      creates++;
      return issue;
    },
    prepareIssue: async () => {
      prepares++;
    },
    insertAssignee: async (saved: typeof issue, id: string) => {
      assert.equal(saved, issue);
      assignmentCalls.push(id);
      if (failures.has(id)) throw new Error('Assignment POST failed');
    },
    checkpoint: (saved: typeof progress) => {
      progress = saved;
    },
  };
  return {
    issue,
    operations,
    failures,
    assignmentCalls,
    get progress() {
      return progress;
    },
    get creates() {
      return creates;
    },
    get prepares() {
      return prepares;
    },
  };
}

test('multi-assignee partial failure retains the created issue and confirmed participant; retry saves only the failed participant', async () => {
  const f = fixture();
  const before = JSON.stringify(f.issue);
  await assert.rejects(
    resumeIssueCreation(f.progress, f.operations),
    (error) => {
      assert.ok(error instanceof IssueAssignmentPersistenceError);
      assert.deepEqual(error.failedUserIds, ['dot']);
      return true;
    }
  );
  assert.equal(f.progress.issue, f.issue);
  assert.deepEqual(f.progress.completedAssigneeIds, ['seamus']);
  assert.equal(f.creates, 1);
  assert.equal(f.prepares, 1);

  f.failures.clear();
  // A new invocation uses the composer checkpoint, including after remount.
  assert.equal(await resumeIssueCreation(f.progress, f.operations), f.issue);
  assert.deepEqual(f.assignmentCalls, ['dot', 'seamus', 'dot']);
  assert.deepEqual(f.progress.completedAssigneeIds.sort(), ['dot', 'seamus']);
  assert.equal(f.creates, 1);
  assert.equal(f.prepares, 1);
  assert.equal(JSON.stringify(f.issue), before);
});

test('creation remains pending until every selected assignment persists, even if one rejects first', async () => {
  const f = fixture();
  let resolveSeamus!: () => void;
  const pending = new Promise<void>((resolve) => {
    resolveSeamus = resolve;
  });
  const operations = {
    ...f.operations,
    insertAssignee: async (issue: typeof f.issue, id: string) => {
      if (id === 'seamus') await pending;
      await f.operations.insertAssignee(issue, id);
    },
  };
  let settled = false;
  const result = resumeIssueCreation(f.progress, operations).finally(() => {
    settled = true;
  });
  // Attach the rejection handler before releasing the delayed POST.
  const rejected = assert.rejects(result, IssueAssignmentPersistenceError);
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(settled, false);
  assert.equal(f.progress.issue, f.issue);
  resolveSeamus();
  await rejected;
  assert.deepEqual(f.progress.completedAssigneeIds, ['seamus']);
});

test('multiple failures are reported together and repeated failed retries never recreate the issue', async () => {
  const f = fixture();
  f.failures.add('seamus');
  for (let attempt = 0; attempt < 2; attempt++) {
    await assert.rejects(
      resumeIssueCreation(f.progress, f.operations),
      (error) => {
        assert.ok(error instanceof IssueAssignmentPersistenceError);
        assert.deepEqual(error.failedUserIds, ['dot', 'seamus']);
        return true;
      }
    );
  }
  f.failures.clear();
  await resumeIssueCreation(f.progress, f.operations);
  assert.equal(f.creates, 1);
  assert.equal(f.prepares, 1);
  assert.equal(f.assignmentCalls.length, 6);
});

test('dot-only creation cannot complete silently unassigned; successful retry assigns the saved issue', async () => {
  const f = fixture(['dot']);
  await assert.rejects(
    resumeIssueCreation(f.progress, f.operations),
    IssueAssignmentPersistenceError
  );
  assert.deepEqual(f.progress.completedAssigneeIds, []);
  f.failures.clear();
  await resumeIssueCreation(f.progress, f.operations);
  assert.deepEqual(f.progress.completedAssigneeIds, ['dot']);
  assert.equal(f.creates, 1);
});

test('successful shared, Seamus-only and intentionally unassigned creation preserve the saved issue', async () => {
  for (const ids of [['dot', 'seamus'], ['seamus'], []]) {
    const f = fixture(ids);
    f.failures.clear();
    assert.equal(await resumeIssueCreation(f.progress, f.operations), f.issue);
    assert.deepEqual(f.assignmentCalls, ids);
    assert.equal(f.creates, 1);
    assert.equal(f.issue.hasUnseenActivity, true);
  }
});

test('a synchronous assignment failure is handled alongside other participants and duplicate selection is written once', async () => {
  const f = fixture(['dot', 'seamus', 'seamus']);
  await assert.rejects(
    resumeIssueCreation(f.progress, {
      ...f.operations,
      insertAssignee: (issue, id) => {
        if (id === 'dot') throw new Error('Synchronous insert failed');
        return f.operations.insertAssignee(issue, id);
      },
    }),
    IssueAssignmentPersistenceError
  );
  assert.deepEqual(f.assignmentCalls, ['seamus']);
  assert.deepEqual(f.progress.completedAssigneeIds, ['seamus']);
});

test('attachment preparation failure keeps saved identity for retry before writing assignments', async () => {
  const f = fixture();
  await assert.rejects(
    resumeIssueCreation(f.progress, {
      ...f.operations,
      prepareIssue: async () => {
        throw new Error('Attachment commit failed');
      },
    }),
    /Attachment commit failed/
  );
  assert.equal(f.progress.issue, f.issue);
  assert.equal(f.progress.prepared, false);
  assert.deepEqual(f.assignmentCalls, []);
  f.failures.clear();
  await resumeIssueCreation(f.progress, f.operations);
  assert.equal(f.creates, 1);
});

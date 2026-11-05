import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  projectDotNotices,
  openProjectDotChat,
  getProjectChatRequest,
  consumeProjectChatRequest,
  subscribeProjectChatRequest,
} from './dotProjectNotices.ts';

test('project unread rows are positive, independent, unique and future-project safe', () => {
  const projects = [{ id: 'p', name: 'Project Alpha' }];
  const counts = [
    { project_id: 'p', unread_count: 3 },
    { project_id: 'zero', unread_count: 0 },
    { project_id: 'future', unread_count: 2 },
    { project_id: 'p', unread_count: 3 },
  ];
  const before = JSON.stringify(counts);
  assert.deepEqual(projectDotNotices(counts, projects), [
    { projectId: 'p', name: 'Project Alpha', unreadCount: 3 },
    { projectId: 'future', name: 'Project future', unreadCount: 2 },
  ]);
  assert.deepEqual(
    projectDotNotices([{ project_id: 'p', unread_count: 0 }], projects),
    []
  );
  assert.equal(
    projectDotNotices([{ project_id: 'p', unread_count: 7 }], projects)[0]
      .unreadCount,
    7
  );
  assert.equal(JSON.stringify(counts), before);
});
test('notice navigation requests the exact project; stale consumption cannot steal a newer request', () => {
  const destinations: string[] = [];
  let changes = 0;
  const unsub = subscribeProjectChatRequest(() => changes++);
  openProjectDotChat('p', (id) => destinations.push(id));
  const first = getProjectChatRequest()!;
  openProjectDotChat('other', (id) => destinations.push(id));
  const last = getProjectChatRequest()!;
  consumeProjectChatRequest(first);
  assert.equal(getProjectChatRequest(), last);
  consumeProjectChatRequest(last);
  assert.equal(getProjectChatRequest(), null);
  assert.deepEqual(destinations, ['p', 'other']);
  assert.equal(changes, 3);
  unsub();
});

test('an already mounted project chat keeps its sheet/history and still receives a new chat request', () => {
  const destinations: string[] = [];
  openProjectDotChat('same', (id) => destinations.push(id), 'same');
  assert.equal(destinations.length, 0);
  const first = getProjectChatRequest()!;
  openProjectDotChat('same', (id) => destinations.push(id), 'same');
  assert.ok(getProjectChatRequest()!.sequence > first.sequence);
  consumeProjectChatRequest(getProjectChatRequest()!);
});

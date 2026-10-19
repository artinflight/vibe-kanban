// Read-only, paginated synthetic transport for the real Dot container.
import assert from 'node:assert/strict';
export function attentionState() {
  return {
    messages: Array.from({ length: 125 }, (_, i) => ({
      id: 'attention-' + (i + 1),
      seq: i + 1,
      role: 'dot',
      body:
        'Retained message ' +
        (i + 1) +
        (i === 60 ? '\nLong flagged context. '.repeat(80) : ''),
      workspace: '11111111-1111-4111-8111-111111111111',
      created: 1792281600 + i,
      seen: false,
      manual_unread: true,
      attention: [3, 61, 112].includes(i + 1)
        ? { kind: i === 60 ? 'action' : 'question', resolved: false }
        : i === 0
          ? { kind: 'question', resolved: true }
          : null,
    })),
    requests: [],
    reads: [],
    hold: null,
    fail: false,
  };
}
export function attentionTransport(s) {
  return async (url, options = {}) => {
    const request = { url, method: options.method ?? 'GET' };
    s.requests.push(request);
    const response = (body, status = 200) => ({
      ok: status === 200,
      status,
      json: async () => body,
    });
    if (url === '/api/dot-sidechat/session')
      return response({
        csrf: 'fixture',
        session_id: 'fixture',
        expires: null,
      });
    if (url === '/api/dot-sidechat/notifications')
      return response({ issues: [], projects: [], workspaces: [] });
    assert.ok(
      url.startsWith('/api/dot-sidechat/thread?'),
      'Navigation must not mutate flags, unread, or send messages'
    );
    assert.equal(request.method, 'GET');
    const query = new URL(url, 'http://fixture').searchParams;
    const after = Number(query.get('after') ?? 0),
      through = Number(query.get('through') ?? s.messages.length);
    const messages = s.messages
      .filter((m) => m.seq > after && m.seq <= through)
      .slice(0, 50);
    if (s.hold && after >= 50) await s.hold;
    if (s.fail) return response({}, 503);
    return response({
      thread: {
        id: query.has('project')
          ? 'project-attention-thread'
          : 'issue-attention-thread',
      },
      scope: {
        issue_label: 'Synthetic attention history',
        workspace_label: 'Selected fixture context',
      },
      messages: structuredClone(messages),
      receipts: {},
      through,
      next_after:
        after + messages.length < through ? messages.at(-1).seq : null,
      capabilities: {
        notifications: true,
        manual_unread: true,
        message_replies: true,
      },
    });
  };
}

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  DotSidechatPanel,
  type SidechatMessage,
  type SidechatReceipt,
} from '@vibe/ui/components/DotSidechatPanel';
import './dot-sidechat.css';

export type Session = {
  csrf: string;
  expires: number | null;
  session_id: string;
};
type Pending = {
  thread?: string;
  workspace?: string;
  project?: string;
  request: string;
  body: string;
  in_reply_to?: string;
};
type Snapshot = {
  thread: { id: string };
  scope: {
    issue_label: string;
    workspace_label: string;
    previous_threads?: { thread_id: string; issue_id: string; issue_label: string }[];
  };
  messages: SidechatMessage[];
  receipts: Record<string, SidechatReceipt>;
  through: number;
  next_after: number | null;
  capabilities?: {
    notifications: boolean;
    manual_unread?: boolean;
    message_replies?: boolean;
  };
};
export class PairingRequired extends Error {}

export async function dotApi(
  path: string,
  signal: AbortSignal,
  body?: unknown,
  csrf?: string
) {
  const response = await fetch('/api/dot-sidechat/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    redirect: 'error',
    signal,
    headers: {
      'X-Dot-Request': '1',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(csrf ? { 'X-Dot-CSRF': csrf } : {}),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (response.status === 401)
    throw new PairingRequired('Pair this browser to continue.');
  if (response.status === 409 && path === 'send')
    throw new Error(
      'Choose the original conversation before retrying this retained message. Its text and request are unchanged.'
    );
  if (response.status === 409)
    throw new Error(
      'This entry changed elsewhere. Cancel this edit, refresh, and review the latest version before saving.'
    );
  if (
    !response.ok &&
    (path.startsWith('project-') || path.startsWith('thread?project='))
  )
    throw new Error(
      'Project collaboration is unavailable. This feature requires the project sidebar Dot service release and access to this project.'
    );
  if (!response.ok)
    throw new Error(
      'Private chat is unavailable or this workspace is outside your access. Your pending message is retained.'
    );
  return response.json();
}

type ChatTarget = { workspaceId?: string; projectId?: string };
type RetainedDraft = { body: string; reply: string | null };
// Owner-session/context scoped fallback when tab storage is temporarily unavailable.
const draftCache = new Map<string, RetainedDraft>();

export function DotSidechatLive(props: ChatTarget) {
  // A destination change gets a fresh lifetime, snapshot and pending-send state.
  // Even callers without their own React key cannot reuse old-context responses.
  const key =
    props.workspaceId && !props.projectId
      ? 'workspace:' + props.workspaceId
      : props.projectId && !props.workspaceId
        ? 'project:' + props.projectId
        : 'none';
  return <DotSidechatSession key={key} {...(key === 'none' ? {} : props)} />;
}

function DotSidechatSession({ workspaceId, projectId }: ChatTarget) {
  const contextId = projectId ?? workspaceId;
  const targetKey = projectId ? 'project' : 'workspace';
  const [historyThread, setHistoryThread] = useState<string | null>(null);
  // All read/manual-attention handlers share this exact thread target. Sending
  // stays disabled for history, so current pending drafts retain their scope.
  const target = useMemo(
    () =>
      projectId
        ? { project: projectId }
        : {
            workspace: workspaceId,
            ...(historyThread ? { thread: historyThread } : {}),
          },
    [projectId, workspaceId, historyThread]
  );
  const query = targetKey + '=' + encodeURIComponent(contextId ?? '');
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [code, setCode] = useState('');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [previousThreads, setPreviousThreads] = useState<
    NonNullable<Snapshot['scope']['previous_threads']>
  >([]);
  const viewQuery =
    historyThread && workspaceId
      ? 'history?workspace=' +
        encodeURIComponent(workspaceId) +
        '&thread=' +
        encodeURIComponent(historyThread)
      : 'thread?' + query;
  const activeView = useRef(viewQuery);
  activeView.current = viewQuery;
  useEffect(() => {
    setHistoryThread(null);
    setPreviousThreads([]);
    setSnapshot(null);
  }, [workspaceId, projectId]);
  const [draft, setDraft] = useState('');
  const [replyTargetId, setReplyTargetId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<Pending | null>(null);
  const retainedDraft = useRef<RetainedDraft>({ body: '', reply: null });
  // Protect a manual choice from older visibility acknowledgements and snapshots.
  const manualUnread = useRef(new Set<string>());
  const readStateRevision = useRef(0);
  const busy = useRef(false);
  const refreshing = useRef<string | null>(null);
  const lifetime = useRef(new AbortController());
  const storageKey =
    session && contextId
      ? 'vibe-dot-pending:' +
        session.session_id +
        ':' +
        (projectId ? 'project:' : '') +
        contextId
      : null;

  const draftKey =
    storageKey?.replace('vibe-dot-pending:', 'vibe-dot-draft:') ?? null;
  function retainDraft(value: RetainedDraft) {
    retainedDraft.current = value;
    setDraft(value.body);
    setReplyTargetId(value.reply);
    if (!draftKey) return;
    draftCache.set(draftKey, value);
    try {
      sessionStorage.setItem(draftKey, JSON.stringify(value));
    } catch {
      setError(
        'Draft retained in this tab, but tab storage is unavailable for reload recovery.'
      );
    }
  }
  function clearRetainedDraft() {
    retainedDraft.current = { body: '', reply: null };
    if (!draftKey) return;
    draftCache.delete(draftKey);
    sessionStorage.removeItem(draftKey);
  }

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void dotApi('session', controller.signal)
      .then((value: Session) => {
        if (!controller.signal.aborted) setSession(value);
      })
      .catch((failure: Error) => {
        if (!controller.signal.aborted && !(failure instanceof PairingRequired))
          setError(failure.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setChecking(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    pending.current = null;
    setDraft('');
    setReplyTargetId(null);
    retainedDraft.current = { body: '', reply: null };
    if (!storageKey || !draftKey) return;
    try {
      const cached = draftCache.get(draftKey);
      const savedDraft = cached ? null : sessionStorage.getItem(draftKey);
      const value: RetainedDraft | null =
        cached ?? (savedDraft ? JSON.parse(savedDraft) : null);
      if (
        value &&
        typeof value.body === 'string' &&
        (value.reply === null || typeof value.reply === 'string')
      ) {
        retainedDraft.current = value;
        setDraft(value.body);
        setReplyTargetId(value.reply);
      }
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const value = JSON.parse(saved) as Pending;
        if (
          (projectId
            ? value.project === projectId && !value.workspace
            : value.workspace === workspaceId && !value.project) &&
          (value.thread === undefined || typeof value.thread === 'string') &&
          typeof value.body === 'string' &&
          typeof value.request === 'string' &&
          (value.in_reply_to === undefined ||
            (typeof value.in_reply_to === 'string' &&
              value.in_reply_to.length > 0))
        ) {
          pending.current = value;
          retainedDraft.current = {
            body: value.body,
            reply: value.in_reply_to ?? null,
          };
          setDraft(value.body);
          setReplyTargetId(value.in_reply_to ?? null);
        }
      }
    } catch {
      setError(
        'This browser cannot retain an uncertain send across reloads. Enable tab storage before sending.'
      );
    }
  }, [storageKey, draftKey, workspaceId, projectId]);

  const refresh = useCallback(async () => {
    if (!session || !contextId || refreshing.current === viewQuery) return;
    const selectedView = viewQuery;
    refreshing.current = selectedView;
    const signal = lifetime.current.signal;
    const revision = readStateRevision.current;
    try {
      let page: Snapshot = await dotApi(selectedView, signal);
      const messages = [...page.messages];
      const receipts = { ...page.receipts };
      while (page.next_after !== null) {
        page = await dotApi(
          selectedView +
            '&after=' +
            page.next_after +
            '&through=' +
            page.through,
          signal
        );
        messages.push(...page.messages);
        Object.assign(receipts, page.receipts);
      }
      if (!signal.aborted && revision === readStateRevision.current && activeView.current === selectedView) {
        setPreviousThreads(page.scope.previous_threads ?? []);
        setSnapshot({ ...page, messages, receipts });
        setError(null);
      }
    } catch (failure) {
      if (!signal.aborted && revision === readStateRevision.current && activeView.current === selectedView) {
        setSnapshot(null);
        if (failure instanceof PairingRequired) {
          setSession(null);
          setSnapshot(null);
        }
        setError((failure as Error).message);
      }
    } finally {
      if (refreshing.current === selectedView) refreshing.current = null;
      if (!signal.aborted && activeView.current === selectedView) setLoading(false);
    }
  }, [session, contextId, viewQuery]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const readReplies = useCallback(
    async (messages: string[]) => {
      if (!session || !contextId) return;
      try {
        const result: { seen: string[] } = await dotApi(
          'seen',
          lifetime.current.signal,
          {
            ...target,
            messages,
          },
          session.csrf
        );
        setSnapshot((previous) =>
          previous
            ? {
                ...previous,
                messages: previous.messages.map((m) =>
                  result.seen.includes(m.id) &&
                  !manualUnread.current.has(m.id) &&
                  !m.manual_unread
                    ? { ...m, seen: true }
                    : m
                ),
              }
            : previous
        );
        window.dispatchEvent(new CustomEvent('dot-sidechat-changed'));
      } catch (failure) {
        if (!lifetime.current.signal.aborted)
          setError((failure as Error).message);
        throw failure;
      }
    },
    [session, contextId, target]
  );

  async function changeReadState(message: string, action: 'read' | 'unread') {
    if (!session || !contextId) return;
    readStateRevision.current++;
    if (action === 'unread') manualUnread.current.add(message);
    try {
      const result: { seen: boolean; manual_unread: boolean } = await dotApi(
        'read-state',
        lifetime.current.signal,
        { ...target, message, action },
        session.csrf
      );
      readStateRevision.current++;
      if (action === 'read') manualUnread.current.delete(message);
      setSnapshot((previous) =>
        previous
          ? {
              ...previous,
              messages: previous.messages.map((m) =>
                m.id === message ? { ...m, ...result } : m
              ),
            }
          : previous
      );
      window.dispatchEvent(new CustomEvent('dot-sidechat-changed'));
    } catch (failure) {
      if (action === 'unread') manualUnread.current.delete(message);
      if (!lifetime.current.signal.aborted)
        setError((failure as Error).message);
      throw failure;
    }
  }

  async function attention(
    message: string,
    action: 'action' | 'resolve' | 'reopen'
  ) {
    if (!session || !contextId) return;
    try {
      await dotApi(
        'attention',
        lifetime.current.signal,
        {
          ...target,
          message,
          action,
        },
        session.csrf
      );
      window.dispatchEvent(new CustomEvent('dot-sidechat-changed'));
      await refresh();
    } catch (failure) {
      if (!lifetime.current.signal.aborted)
        setError((failure as Error).message);
    }
  }

  async function pair() {
    if (busy.current) return;
    busy.current = true;
    setSending(true);
    try {
      const value: Session = await dotApi('pair', lifetime.current.signal, {
        code,
      });
      setCode('');
      setSnapshot(null);
      setError(null);
      setSession(value);
      window.dispatchEvent(
        new CustomEvent('dot-sidechat-changed', { detail: { reset: true } })
      );
      setLoading(true);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      busy.current = false;
      setSending(false);
    }
  }

  async function send() {
    if (
      (historyThread && !pending.current) ||
      !snapshot?.thread.id ||
      !session ||
      !contextId ||
      !storageKey ||
      busy.current ||
      lifetime.current.signal.aborted ||
      !draft.trim() ||
      loading
    )
      return;
    if (pending.current?.thread && pending.current.thread !== snapshot.thread.id) {
      setError('Choose the original conversation to retry this retained message.');
      return;
    }
    busy.current = true;
    setSending(true);
    try {
      if (
        (replyTargetId || pending.current?.in_reply_to) &&
        !snapshot?.capabilities?.message_replies
      )
        throw new Error(
          'Reply targeting is unavailable. Your reply is retained; refresh after the Dot service release.'
        );
      const outgoing = pending.current ?? {
        ...target,
        thread: snapshot.thread.id,
        request: crypto.randomUUID(),
        body: draft,
        ...(replyTargetId ? { in_reply_to: replyTargetId } : {}),
      };
      // A legacy unbound draft can be bound only after choosing its original
      // history. Otherwise the server reconciles an existing receipt or refuses.
      if (!outgoing.thread && historyThread) outgoing.thread = historyThread;
      // Persist BEFORE submitting; retries retain exact thread, key and body.
      sessionStorage.setItem(storageKey, JSON.stringify(outgoing));
      pending.current = outgoing;
      const saved = await dotApi('send', lifetime.current.signal, outgoing, session.csrf);
      sessionStorage.removeItem(storageKey);
      clearRetainedDraft();
      pending.current = null;
      setDraft('');
      setReplyTargetId(null);
      if (workspaceId && typeof saved.thread === 'string' && saved.thread !== snapshot.thread.id)
        setHistoryThread(saved.thread);
      await refresh();
    } catch (failure) {
      setError((failure as Error).message);
      if (failure instanceof PairingRequired) {
        setSession(null);
        setSnapshot(null);
      }
    } finally {
      busy.current = false;
      setSending(false);
    }
  }

  async function logout() {
    if (!session || busy.current) return;
    busy.current = true;
    try {
      await dotApi('logout', lifetime.current.signal, {}, session.csrf);
      lifetime.current.abort();
      lifetime.current = new AbortController();
      if (storageKey) sessionStorage.removeItem(storageKey);
      if (session) {
        const prefix = 'vibe-dot-draft:' + session.session_id + ':';
        for (const key of [...draftCache.keys()])
          if (key.startsWith(prefix)) draftCache.delete(key);
        for (let index = sessionStorage.length - 1; index >= 0; index--) {
          const key = sessionStorage.key(index);
          if (key?.startsWith(prefix)) sessionStorage.removeItem(key);
        }
      }
      pending.current = null;
      setDraft('');
      setReplyTargetId(null);
      setSnapshot(null);
      setSession(null);
      window.dispatchEvent(
        new CustomEvent('dot-sidechat-changed', { detail: { reset: true } })
      );
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      busy.current = false;
    }
  }

  if (checking)
    return (
      <div className="dot-access" role="status">
        Checking private chat access…
      </div>
    );
  if (!session)
    return (
      <section className="dot-access" aria-label="Pair private Dot chat">
        <h3>Private chat with Dot</h3>
        <p>
          Pair this browser with a one-use code from your Vibe administrator.
          Access stays valid until you disconnect or it is revoked, and covers
          only the approved projects.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void pair();
          }}
        >
          <label htmlFor="dot-pair">Pairing code</label>
          <input
            id="dot-pair"
            type="password"
            autoComplete="off"
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
          <button type="submit" disabled={sending || !code.trim()}>
            Pair browser
          </button>
        </form>
        {error && <p role="alert">{error}</p>}
      </section>
    );
  return (
    <div className="dot-fixture-container">
      <div className="dot-session">
        <span>Private browser session</span>
        <button type="button" onClick={() => void logout()}>
          Disconnect
        </button>
      </div>
      {!projectId && previousThreads.length > 0 && (
        <label className="dot-session">
          Conversation
          <select
            aria-label="Dot conversation history"
            value={historyThread ?? ''}
            onChange={(event) => {
              setSnapshot(null);
              setLoading(true);
              setHistoryThread(event.target.value || null);
            }}
          >
            <option value="">Current conversation</option>
            {previousThreads.map((previous) => (
              <option key={previous.thread_id} value={previous.thread_id}>
                {previous.issue_label}
              </option>
            ))}
          </select>
        </label>
      )}
      {!contextId ? (
        <div className="dot-access">
          Select an issue-linked workspace to chat with Dot.
        </div>
      ) : (
        <DotSidechatPanel
          live
          historyOnly={historyThread !== null && pending.current === null}
          notificationsEnabled={snapshot?.capabilities?.notifications ?? false}
          onRead={readReplies}
          onReadState={
            snapshot?.capabilities?.manual_unread ? changeReadState : undefined
          }
          onReplyTarget={(message) => {
            if (!busy.current && !pending.current)
              retainDraft({ ...retainedDraft.current, reply: message });
          }}
          replyEnabled={snapshot?.capabilities?.message_replies ?? false}
          replyTarget={(() => {
            const message = snapshot?.messages.find(
              (m) => m.id === replyTargetId
            );
            return message
              ? {
                  id: message.id,
                  seq: message.seq,
                  role: message.role,
                  created: message.created,
                  excerpt: message.body.slice(0, 1000),
                  truncated: message.body.length > 1000,
                }
              : null;
          })()}
          onAttention={(message, action) => void attention(message, action)}
          messages={snapshot?.messages ?? []}
          receipts={snapshot?.receipts ?? {}}
          projectScope={!!projectId}
          issueLabel={
            snapshot?.scope.issue_label ??
            (projectId ? 'Project conversation' : 'Issue conversation')
          }
          workspaceLabel={snapshot?.scope.workspace_label ?? contextId ?? ''}
          threadId={snapshot?.thread.id ?? ''}
          loading={loading}
          sending={sending}
          error={error}
          draft={draft}
          draftLocked={pending.current !== null}
          onDraft={(body) => retainDraft({ ...retainedDraft.current, body })}
          onSend={() => void send()}
          onRefresh={() => void refresh()}
        />
      )}
    </div>
  );
}

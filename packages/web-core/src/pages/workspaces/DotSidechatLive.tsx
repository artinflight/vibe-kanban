import { useCallback, useEffect, useRef, useState } from 'react';
import {
  DotSidechatPanel,
  type SidechatMessage,
  type SidechatReceipt,
} from '@vibe/ui/components/DotSidechatPanel';
import './dot-sidechat.css';

type Session = { csrf: string; expires: number | null; session_id: string };
type Pending = { workspace: string; request: string; body: string };
type Snapshot = {
  thread: { id: string };
  scope: { issue_label: string; workspace_label: string };
  messages: SidechatMessage[];
  receipts: Record<string, SidechatReceipt>;
  through: number;
  next_after: number | null;
};
class PairingRequired extends Error {}

async function api(
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
  if (!response.ok)
    throw new Error(
      'Private chat is unavailable or this workspace is outside your access. Your pending message is retained.'
    );
  return response.json();
}

export function DotSidechatLive({ workspaceId }: { workspaceId?: string }) {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [code, setCode] = useState('');
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<Pending | null>(null);
  const busy = useRef(false);
  const refreshing = useRef(false);
  const lifetime = useRef(new AbortController());
  const storageKey =
    session && workspaceId
      ? 'vibe-dot-pending:' + session.session_id + ':' + workspaceId
      : null;

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void api('session', controller.signal)
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
    if (!storageKey) return;
    try {
      const saved = sessionStorage.getItem(storageKey);
      if (saved) {
        const value = JSON.parse(saved) as Pending;
        if (
          value.workspace === workspaceId &&
          typeof value.body === 'string' &&
          typeof value.request === 'string'
        ) {
          pending.current = value;
          setDraft(value.body);
        }
      }
    } catch {
      setError(
        'This browser cannot retain an uncertain send across reloads. Enable tab storage before sending.'
      );
    }
  }, [storageKey, workspaceId]);

  const refresh = useCallback(async () => {
    if (!session || !workspaceId || refreshing.current) return;
    refreshing.current = true;
    const signal = lifetime.current.signal;
    try {
      let page: Snapshot = await api(
        'thread?workspace=' + encodeURIComponent(workspaceId),
        signal
      );
      const messages = [...page.messages];
      const receipts = { ...page.receipts };
      while (page.next_after !== null) {
        page = await api(
          'thread?workspace=' +
            encodeURIComponent(workspaceId) +
            '&after=' +
            page.next_after +
            '&through=' +
            page.through,
          signal
        );
        messages.push(...page.messages);
        Object.assign(receipts, page.receipts);
      }
      if (!signal.aborted) {
        setSnapshot({ ...page, messages, receipts });
        setError(null);
      }
    } catch (failure) {
      if (!signal.aborted) {
        setSnapshot(null);
        if (failure instanceof PairingRequired) {
          setSession(null);
          setSnapshot(null);
        }
        setError((failure as Error).message);
      }
    } finally {
      refreshing.current = false;
      if (!signal.aborted) setLoading(false);
    }
  }, [session, workspaceId]);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  async function pair() {
    if (busy.current) return;
    busy.current = true;
    setSending(true);
    try {
      const value: Session = await api('pair', lifetime.current.signal, {
        code,
      });
      setCode('');
      setSnapshot(null);
      setError(null);
      setSession(value);
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
      !session ||
      !workspaceId ||
      !storageKey ||
      busy.current ||
      !draft.trim()
    )
      return;
    busy.current = true;
    setSending(true);
    try {
      const outgoing = pending.current ?? {
        workspace: workspaceId,
        request: crypto.randomUUID(),
        body: draft,
      };
      // Persist BEFORE submitting; retries after a lost response reuse the exact key/body.
      sessionStorage.setItem(storageKey, JSON.stringify(outgoing));
      pending.current = outgoing;
      await api('send', lifetime.current.signal, outgoing, session.csrf);
      sessionStorage.removeItem(storageKey);
      pending.current = null;
      setDraft('');
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
      await api('logout', lifetime.current.signal, {}, session.csrf);
      lifetime.current.abort();
      lifetime.current = new AbortController();
      if (storageKey) sessionStorage.removeItem(storageKey);
      pending.current = null;
      setDraft('');
      setSnapshot(null);
      setSession(null);
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
          Access stays valid until you disconnect or it is revoked, and covers only the approved projects.
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
      {!workspaceId ? (
        <div className="dot-access">
          Select an issue-linked workspace to chat with Dot.
        </div>
      ) : (
        <DotSidechatPanel
          live
          messages={snapshot?.messages ?? []}
          receipts={snapshot?.receipts ?? {}}
          issueLabel={snapshot?.scope.issue_label ?? 'Issue conversation'}
          workspaceLabel={snapshot?.scope.workspace_label ?? workspaceId}
          threadId={snapshot?.thread.id ?? ''}
          loading={loading}
          sending={sending}
          error={error}
          draft={draft}
          draftLocked={pending.current !== null}
          onDraft={setDraft}
          onSend={() => void send()}
          onRefresh={() => void refresh()}
        />
      )}
    </div>
  );
}

import { useCallback, useEffect, useRef, useState } from 'react';
import {
  DotSidechatPanel,
  type SidechatMessage,
  type SidechatReceipt,
} from '@vibe/ui/components/DotSidechatPanel';
import './dot-sidechat.css';

interface Snapshot {
  thread: { id: string };
  messages: SidechatMessage[];
  receipts: Record<string, SidechatReceipt>;
}

async function request(path: string, body?: unknown) {
  const response = await fetch(
    '/__dot_fixture/' + path,
    body === undefined
      ? undefined
      : {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
  );
  if (!response.ok)
    throw new Error('Fixture unavailable; your draft is retained.');
  return response.json();
}

export function DotSidechatFixture() {
  const [snapshot, setSnapshot] = useState<Snapshot>({
    thread: { id: '' },
    messages: [],
    receipts: {},
  });
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pending = useRef<{ request: string; body: string } | null>(null);
  const sendingRef = useRef(false);
  const refresh = useCallback(async () => {
    try {
      setSnapshot(await request('thread'));
      setError(null);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void refresh();
  }, [refresh]);
  const send = async () => {
    if (sendingRef.current || !draft.trim()) return;
    if (pending.current && pending.current.body !== draft) {
      setError(
        'A previous send is uncertain. Restore its draft and retry with the same request ID, or check retained history first.'
      );
      return;
    }
    const outgoing = pending.current ?? {
      request: crypto.randomUUID(),
      body: draft,
    };
    pending.current = outgoing;
    sendingRef.current = true;
    setSending(true);
    try {
      await request('send', outgoing);
      pending.current = null;
      setDraft('');
      await refresh();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  };
  const simulate = async (kind: 'accept' | 'reply') => {
    const message = snapshot.messages.find(
      (item) =>
        item.role === 'owner' && !snapshot.receipts[item.id]?.reply_persisted
    );
    if (kind === 'reply' && !message) return;
    try {
      await request(
        kind,
        kind === 'accept'
          ? {}
          : { message: message!.id, request: crypto.randomUUID() }
      );
      await refresh();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  useEffect(() => {
    const params = new URLSearchParams(window.location.hash.slice(1));
    const target = params.get('message');
    if (target && params.get('thread') === snapshot.thread.id) {
      document
        .getElementById('message-' + target)
        ?.scrollIntoView({ block: 'center' });
    }
  }, [snapshot]);
  return (
    <div className="dot-fixture-container">
      <DotSidechatPanel
        messages={snapshot.messages}
        receipts={snapshot.receipts}
        issueLabel="VK · Private issue conversation"
        workspaceLabel="Disposable prototype"
        threadId={snapshot.thread.id}
        loading={loading}
        sending={sending}
        error={error}
        draft={draft}
        onDraft={setDraft}
        onSend={() => void send()}
        onRefresh={() => void refresh()}
      />
      <details className="dot-test-controls">
        <summary>Fixture controls · no external delivery</summary>
        <button type="button" onClick={() => void simulate('accept')}>
          Simulate webhook acceptance
        </button>
        <button type="button" onClick={() => void simulate('reply')}>
          Append labeled fixture reply
        </button>
      </details>
    </div>
  );
}

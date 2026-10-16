import { useEffect, useRef, useState } from 'react';

export interface SidechatMessage {
  id: string;
  seq: number;
  role: 'owner' | 'dot';
  body: string;
  workspace: string;
  created: number;
}

export interface SidechatReceipt {
  state: string;
  reply_persisted: boolean;
}

export interface DotSidechatPanelProps {
  live?: boolean;
  draftLocked?: boolean;
  messages: SidechatMessage[];
  receipts: Record<string, SidechatReceipt>;
  issueLabel: string;
  workspaceLabel: string;
  threadId: string;
  loading: boolean;
  sending: boolean;
  error: string | null;
  draft: string;
  onDraft: (value: string) => void;
  onSend: () => void;
  onRefresh: () => void;
}

function deliveryLabel(receipt?: SidechatReceipt) {
  if (!receipt) return 'Saved';
  if (receipt.reply_persisted) return 'Reply persisted';
  if (receipt.state === 'webhook_accepted')
    return 'Webhook accepted · awaiting reply';
  if (receipt.state === 'inflight')
    return 'Delivery in progress · reply unconfirmed';
  if (receipt.state === 'failed') return 'Delivery failed · message retained';
  return 'Saved · awaiting delivery';
}

export function DotSidechatPanel(props: DotSidechatPanelProps) {
  const history = useRef<HTMLDivElement>(null);
  const [followLatest, setFollowLatest] = useState(true);
  useEffect(() => {
    if (followLatest && history.current)
      history.current.scrollTop = history.current.scrollHeight;
  }, [props.messages.length, followLatest]);

  useEffect(() => {
    const reveal = () => {
      const link = new URLSearchParams(window.location.hash.slice(1));
      if (link.get('thread') !== props.threadId) return;
      const message = link.get('message');
      if (!message || !props.messages.some((item) => item.id === message))
        return;
      setFollowLatest(false);
      document
        .getElementById('message-' + message)
        ?.scrollIntoView({ block: 'center' });
    };
    reveal();
    window.addEventListener('hashchange', reveal);
    return () => window.removeEventListener('hashchange', reveal);
  }, [props.threadId, props.messages]);

  return (
    <section
      className="dot-panel bg-secondary text-normal"
      aria-label="Private Dot conversation"
    >
      <header className="dot-heading">
        <div>
          <span className="dot-orb" aria-hidden="true" />
          <strong>Dot</strong>
          <span className="dot-private">Private</span>
        </div>
        <button
          type="button"
          aria-label="Refresh conversation"
          onClick={props.onRefresh}
        >
          ↻
        </button>
      </header>
      <div className="dot-scope">
        <strong>{props.issueLabel}</strong>
        <span>Workspace context: {props.workspaceLabel}</span>
      </div>
      {!props.live && (
        <div className="dot-fixture">
          Isolated prototype · fixture replies only
        </div>
      )}
      <div
        ref={history}
        className="dot-history"
        role="log"
        aria-live="polite"
        onScroll={() => {
          const node = history.current;
          if (node)
            setFollowLatest(
              node.scrollHeight - node.scrollTop - node.clientHeight < 48
            );
        }}
      >
        {props.loading && <p role="status">Loading retained conversation…</p>}
        {!props.loading && props.messages.length === 0 && (
          <div className="dot-empty">
            <span className="dot-empty-orb">●</span>
            <h3>A little space to think together.</h3>
            <p>
              Talk through this issue with Dot. Your coding agent stays focused
              on its own work.
            </p>
            <p className="dot-muted">
              {props.live
                ? 'Messages stay in this private issue thread across workspaces.'
                : 'This preview stores fixture messages only.'}
            </p>
          </div>
        )}
        {props.messages.map((message) => (
          <article
            key={message.id}
            id={'message-' + message.id}
            className={'dot-message dot-message-' + message.role}
          >
            <div className="dot-byline">
              <strong>
                {message.role === 'owner'
                  ? 'You'
                  : props.live
                    ? 'Dot'
                    : 'Dot · fixture'}
              </strong>
              <a
                aria-label={'Link to message ' + message.seq}
                href={'#thread=' + props.threadId + '&message=' + message.id}
              >
                #{message.seq}
              </a>
            </div>
            <p>{message.body}</p>
            {message.role === 'owner' && (
              <small>{deliveryLabel(props.receipts[message.id])}</small>
            )}
          </article>
        ))}
      </div>
      {!followLatest && (
        <button
          type="button"
          className="dot-latest"
          onClick={() => setFollowLatest(true)}
        >
          Jump to latest ↓
        </button>
      )}
      {props.error && (
        <div role="alert" className="dot-error">
          {props.error}{' '}
          <button type="button" onClick={props.onRefresh}>
            Check history
          </button>
        </div>
      )}
      <form
        className="dot-composer"
        onSubmit={(event) => {
          event.preventDefault();
          props.onSend();
        }}
      >
        <label className="dot-sr-only" htmlFor="dot-draft">
          Message Dot
        </label>
        <textarea
          id="dot-draft"
          readOnly={props.draftLocked}
          value={props.draft}
          onChange={(event) => props.onDraft(event.target.value)}
          placeholder="Think through this issue…"
          rows={3}
          maxLength={15000}
          onKeyDown={(event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
              event.preventDefault();
              props.onSend();
            }
          }}
        />
        <div className="dot-composer-actions">
          <span>Ctrl + Enter to send</span>
          <button
            type="submit"
            disabled={props.sending || !props.draft.trim() || props.loading}
          >
            {props.sending
              ? 'Saving…'
              : props.live
                ? props.draftLocked
                  ? 'Retry same message ↑'
                  : 'Send to Dot ↑'
                : 'Send fixture message ↑'}
          </button>
        </div>
        <p className="dot-agent-note">
          {props.live
            ? 'Nothing is forwarded to your coding agent. Use its separate composer to give it instructions.'
            : 'Coding-agent handoff is separate and unavailable in this prototype.'}
        </p>
      </form>
    </section>
  );
}

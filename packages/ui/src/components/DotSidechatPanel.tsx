import { useEffect, useRef, useState } from 'react';

export interface SidechatReplyReference {
  id: string;
  seq: number;
  role: 'owner' | 'dot';
  created: number;
  excerpt: string;
  truncated?: boolean;
  unavailable?: boolean;
}

export interface SidechatMessage {
  id: string;
  seq: number;
  role: 'owner' | 'dot';
  body: string;
  workspace: string;
  created: number;
  seen?: boolean;
  manual_unread?: boolean;
  in_reply_to?: string;
  reply_reference?: SidechatReplyReference;
  dispatch_note?: { workspace_id: string; execution_id: string };
  attention?: { kind: 'question' | 'action'; resolved: boolean } | null;
}

export interface SidechatReceipt {
  state: string;
  reply_persisted: boolean;
}

export interface DotSidechatPanelProps {
  live?: boolean;
  projectScope?: boolean;
  notificationsEnabled?: boolean;
  onRead?: (messages: string[]) => Promise<void>;
  onAttention?: (
    message: string,
    action: 'action' | 'resolve' | 'reopen'
  ) => void;
  onReadState?: (message: string, action: 'read' | 'unread') => Promise<void>;
  draftLocked?: boolean;
  replyTarget?: SidechatReplyReference | null;
  replyEnabled?: boolean;
  onReplyTarget?: (message: string | null) => void;
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

// Stored sidechat timestamps are Unix seconds. Pin the display zone rather than
// inheriting the viewer's device zone; Intl applies Toronto's DST rules.
const messageTime = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/Toronto',
  year: 'numeric',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
});

function MessageTimestamp({ created }: { created: number }) {
  const date = new Date(created * 1000);
  if (!Number.isFinite(date.getTime())) return null;
  return (
    <time dateTime={date.toISOString()} title="Eastern time · America/Toronto">
      {messageTime.format(date)}
    </time>
  );
}

export function DotSidechatPanel(props: DotSidechatPanelProps) {
  const history = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const [followLatest, setFollowLatest] = useState(true);
  const [readStateBusy, setReadStateBusy] = useState(new Set<string>());
  const readStateInFlight = useRef(new Set<string>());
  const readsInFlight = useRef(new Set<string>());
  const readsConfirmed = useRef(new Set<string>());
  useEffect(() => {
    if (!props.live || !props.notificationsEnabled || !props.onRead) return;
    const visibleReplies = () => {
      const root = history.current;
      if (
        !root ||
        document.visibilityState !== 'visible' ||
        !document.hasFocus()
      )
        return;
      const bounds = root.getBoundingClientRect();
      const ids = props.messages
        .filter(
          (m) =>
            m.role === 'dot' &&
            m.seen === false &&
            !m.manual_unread &&
            !readStateInFlight.current.has(m.id) &&
            !readsInFlight.current.has(m.id) &&
            !readsConfirmed.current.has(m.id)
        )
        .filter((m) => {
          const node = root.querySelector<HTMLElement>(
            `[data-dot-read="${CSS.escape(m.id)}"]`
          );
          if (!node || node.getClientRects().length === 0) return false;
          for (
            let parent: HTMLElement | null = node.parentElement;
            parent;
            parent = parent.parentElement
          ) {
            const style = getComputedStyle(parent);
            if (
              parent.hidden ||
              parent.getAttribute('aria-hidden') === 'true' ||
              parent.hasAttribute('inert') ||
              style.display === 'none' ||
              style.visibility === 'hidden' ||
              style.opacity === '0'
            )
              return false;
          }
          const rect = node.getBoundingClientRect();
          // Only the reply's end becoming visible counts. Loading/polling history,
          // a hidden phone tab, or scrolling above a long reply does not read it.
          return (
            rect.height > 0 &&
            rect.width > 0 &&
            rect.top >= Math.max(0, bounds.top) &&
            rect.bottom <= Math.min(window.innerHeight, bounds.bottom) &&
            rect.right > Math.max(0, bounds.left) &&
            rect.left < Math.min(window.innerWidth, bounds.right)
          );
        })
        .map((m) => m.id)
        .slice(0, 100);
      if (!ids.length) return;
      ids.forEach((id) => readsInFlight.current.add(id));
      void props.onRead!(ids)
        .then(() => ids.forEach((id) => readsConfirmed.current.add(id)))
        .catch(() => undefined)
        .finally(() => ids.forEach((id) => readsInFlight.current.delete(id)));
    };
    const observedRoot = history.current;
    const resize =
      typeof ResizeObserver === 'undefined'
        ? null
        : new ResizeObserver(visibleReplies);
    if (observedRoot) resize?.observe(observedRoot);
    const intersection =
      typeof IntersectionObserver === 'undefined'
        ? null
        : new IntersectionObserver(visibleReplies, { threshold: 1 });
    observedRoot
      ?.querySelectorAll('[data-dot-read]')
      .forEach((node) => intersection?.observe(node));
    const frame = requestAnimationFrame(visibleReplies);
    observedRoot?.addEventListener('scroll', visibleReplies);
    window.addEventListener('focus', visibleReplies);
    window.addEventListener('resize', visibleReplies);
    document.addEventListener('visibilitychange', visibleReplies);
    return () => {
      cancelAnimationFrame(frame);
      observedRoot?.removeEventListener('scroll', visibleReplies);
      resize?.disconnect();
      intersection?.disconnect();
      window.removeEventListener('focus', visibleReplies);
      window.removeEventListener('resize', visibleReplies);
      document.removeEventListener('visibilitychange', visibleReplies);
    };
  }, [props.messages, props.live, props.notificationsEnabled, props.onRead]);
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
        <span>
          {props.projectScope ? 'Scope' : 'Workspace context'}:{' '}
          {props.workspaceLabel}
        </span>
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
              Talk through {props.projectScope ? 'this project' : 'this issue'}{' '}
              with Dot. Your coding agent stays focused on its own work.
            </p>
            <p className="dot-muted">
              {props.live
                ? props.projectScope
                  ? 'Messages stay private to you and Dot across this project’s issues and workspaces.'
                  : 'Messages stay in this private issue thread across workspaces.'
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
              <MessageTimestamp created={message.created} />
              {props.onReplyTarget && props.replyEnabled && (
                <button
                  type="button"
                  className="dot-reply-button"
                  aria-label={'Reply to message ' + message.seq}
                  disabled={props.sending || props.draftLocked || props.loading}
                  onClick={() => {
                    props.onReplyTarget?.(message.id);
                    composer.current?.focus();
                  }}
                >
                  Reply to
                </button>
              )}
              {message.dispatch_note && (
                <span className="dot-private">Agent dispatch note</span>
              )}
              <a
                aria-label={'Link to message ' + message.seq}
                href={'#thread=' + props.threadId + '&message=' + message.id}
              >
                #{message.seq}
              </a>
            </div>
            {message.reply_reference && (
              <blockquote className="dot-reply-reference">
                {message.reply_reference.unavailable ? (
                  <span>
                    Reply to #{message.reply_reference.seq} · context in another
                    workspace
                  </span>
                ) : (
                  <>
                    <a
                      href={
                        '#thread=' +
                        props.threadId +
                        '&message=' +
                        message.reply_reference.id
                      }
                    >
                      Reply to{' '}
                      {message.reply_reference.role === 'owner' ? 'you' : 'Dot'}{' '}
                      · #{message.reply_reference.seq}
                    </a>
                    <p>
                      {message.reply_reference.excerpt}
                      {message.reply_reference.truncated ? '…' : ''}
                    </p>
                  </>
                )}
              </blockquote>
            )}
            <p>{message.body}</p>
            {message.role === 'dot' &&
              props.live &&
              props.notificationsEnabled && (
                <div className="dot-reply-actions">
                  {message.attention && (
                    <span className="dot-attention-label">
                      {message.attention.resolved
                        ? 'Resolved'
                        : 'Needs Attention'}{' '}
                      · {message.attention.kind}
                    </span>
                  )}
                  {props.onReadState && (
                    <button
                      type="button"
                      disabled={readStateBusy.has(message.id)}
                      aria-label={
                        message.manual_unread
                          ? 'Mark Dot reply as read'
                          : 'Mark Dot reply as unread'
                      }
                      onClick={() => {
                        if (readStateInFlight.current.has(message.id)) return;
                        readStateInFlight.current.add(message.id);
                        setReadStateBusy(new Set(readStateInFlight.current));
                        void props.onReadState!(
                          message.id,
                          message.manual_unread ? 'read' : 'unread'
                        )
                          .catch(() => undefined)
                          .finally(() => {
                            readStateInFlight.current.delete(message.id);
                            setReadStateBusy(
                              new Set(readStateInFlight.current)
                            );
                          });
                      }}
                    >
                      {message.manual_unread ? 'Mark read' : 'Mark unread'}
                    </button>
                  )}
                  {props.onAttention && (
                    <button
                      type="button"
                      aria-label={
                        message.attention
                          ? `${message.attention.resolved ? 'Reopen' : 'Resolve'} Dot ${message.attention.kind}`
                          : 'Mark Dot reply as needing attention'
                      }
                      onClick={() =>
                        props.onAttention?.(
                          message.id,
                          message.attention
                            ? message.attention.resolved
                              ? 'reopen'
                              : 'resolve'
                            : 'action'
                        )
                      }
                    >
                      {message.attention
                        ? message.attention.resolved
                          ? 'Reopen'
                          : 'Resolve'
                        : 'Needs attention'}
                    </button>
                  )}
                </div>
              )}
            {message.role === 'dot' && (
              <span
                data-dot-read={message.id}
                className="dot-read-marker"
                aria-hidden="true"
              />
            )}
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
        {props.replyTarget && (
          <div
            className="dot-reply-target"
            role="group"
            aria-label="Reply target"
          >
            <div>
              <strong>
                Replying to {props.replyTarget.role === 'owner' ? 'you' : 'Dot'}{' '}
                · #{props.replyTarget.seq}
              </strong>
              <MessageTimestamp created={props.replyTarget.created} />
              <p>
                {props.replyTarget.excerpt}
                {props.replyTarget.truncated ? '…' : ''}
              </p>
            </div>
            <button
              type="button"
              className="dot-reply-button"
              aria-label="Cancel reply"
              disabled={props.sending || props.draftLocked}
              onClick={() => {
                props.onReplyTarget?.(null);
                composer.current?.focus();
              }}
            >
              Cancel
            </button>
          </div>
        )}
        <label className="dot-sr-only" htmlFor="dot-draft">
          Message Dot
        </label>
        <textarea
          ref={composer}
          id="dot-draft"
          readOnly={props.draftLocked}
          value={props.draft}
          onChange={(event) => props.onDraft(event.target.value)}
          placeholder={
            props.projectScope
              ? 'Think through this project…'
              : 'Think through this issue…'
          }
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

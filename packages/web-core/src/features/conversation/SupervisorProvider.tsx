import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import type {
  AcceptConversationMessage,
  SupervisorEvent,
  SupervisorSnapshot,
  ConversationMessage,
  SupervisorRunStatus,
} from 'shared/types';
import { ApiError } from '@/shared/lib/api';
import { createMessageId } from '@/shared/lib/createMessageId';
import { SupervisorContext } from '@/shared/hooks/useSupervisor';
import { supervisorApi } from './api';
import {
  applySupervisorEvent,
  mergeRuns,
  type SupervisorHistory,
} from './supervisor-state';
import { SupervisorPanel } from './SupervisorPanel';

// Mount above the host-keyed route providers: workspace navigation cannot
// replace the supervisor owner, draft, pending retry or connection.
export function SupervisorProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { data: capabilities } = useQuery({
    queryKey: ['supervisor', 'local', 'capabilities'],
    queryFn: supervisorApi.capabilities,
    staleTime: 30_000,
    retry: false,
    refetchInterval: open ? 10_000 : false,
  });
  const [snapshot, setSnapshot] = useState<SupervisorSnapshot | null>(null);
  const [history, setHistory] = useState<SupervisorHistory | null>(null);
  const current = useRef<SupervisorHistory | null>(null);
  const [page, setPage] = useState<ConversationMessage[] | null>(null);
  const [pageRuns, setPageRuns] = useState<SupervisorRunStatus[]>([]);
  const [hasEarlier, setHasEarlier] = useState(true);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState<AcceptConversationMessage | null>(
    null
  );
  const [sending, setSending] = useState(false);
  const [revision, setRevision] = useState(0);
  const [reload, setReload] = useState(0);
  const sendInFlight = useRef(false);
  const launcher = useRef<HTMLElement | null>(null);
  const dataEpoch = useRef(0);

  const publish = useCallback((value: SupervisorHistory) => {
    current.current = value;
    setHistory(value);
  }, []);

  useEffect(() => {
    if (!open || !capabilities?.enabled) return;
    let disposed = false;
    let socket: WebSocket | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let backoff = 1000;
    const schedule = (work: () => void) => {
      if (disposed) return;
      clearTimeout(timer);
      timer = setTimeout(work, backoff);
      backoff = Math.min(backoff * 2, 15000);
    };
    const initialise = async () => {
      setLoading(true);
      setConnected(false);
      setError(null);
      try {
        const next = await supervisorApi.resolve();
        const [messages, runs] = await Promise.all([
          supervisorApi.messages(next.conversation.id),
          supervisorApi.runs(next.conversation.id),
        ]);
        if (disposed) return;
        const old = current.current;
        if (
          old &&
          (old.authorityId !== next.conversation.authority_id ||
            old.principalId !== next.conversation.principal_id ||
            old.conversationId !== next.conversation.id)
        ) {
          setDraft('');
          setPending(null);
        }
        dataEpoch.current += 1;
        setSnapshot(next);
        setPage(null);
        setPageRuns([]);
        setHasEarlier(messages.length === 50);
        publish({
          conversationId: next.conversation.id,
          authorityId: next.conversation.authority_id,
          principalId: next.conversation.principal_id,
          cursor: next.last_seq,
          messages,
          runs,
        });
        setRevision((value) => value + 1);
        void connect();
      } catch (failure) {
        if (!disposed) {
          // A failed owner lookup must not leave a previous principal's text visible.
          current.current = null;
          setHistory(null);
          setSnapshot(null);
          setPage(null);
          if (
            failure instanceof ApiError &&
            (failure.statusCode === 401 || failure.statusCode === 403)
          ) {
            setDraft('');
            setPending(null);
          }
          setError(String(failure));
        }
      } finally {
        if (!disposed) setLoading(false);
      }
    };
    const connect = async () => {
      const value = current.current;
      if (disposed || !value) return;
      try {
        const nextSocket = await supervisorApi.connect(
          value.conversationId,
          value.cursor
        );
        if (disposed) {
          nextSocket.close();
          return;
        }
        socket = nextSocket;
        nextSocket.onopen = () => {
          if (!disposed) {
            setConnected(true);
            backoff = 1000;
          }
        };
        if (nextSocket.readyState === WebSocket.OPEN)
          nextSocket.onopen(new Event('open'));
        nextSocket.onmessage = ({ data }) => {
          if (disposed || nextSocket !== socket) return;
          try {
            const event = JSON.parse(String(data)) as
              | SupervisorEvent
              | { type: 'resync_required' };
            if (event.type === 'resync_required')
              throw new Error('Resynchronise');
            const before = current.current;
            if (!before) return;
            const after = applySupervisorEvent(
              before,
              event as SupervisorEvent
            );
            publish({ ...after, messages: after.messages.slice(-200) });
            if (event.type === 'run.status') {
              const run = (event as SupervisorEvent)
                .payload as SupervisorRunStatus;
              setPageRuns((before) =>
                before.some((item) => item.id === run.id)
                  ? mergeRuns(before, [run])
                  : before
              );
            }
            if (after.messages.length > 200) setHasEarlier(true);
            if (event.type === 'history.cleared') {
              dataEpoch.current += 1;
              setPage(null);
              setPageRuns([]);
              setPending(null);
              setHasEarlier(false);
            }
            if (
              event.type === 'memory.changed' ||
              event.type === 'memory.forgotten' ||
              event.type.startsWith('action.') ||
              event.type.startsWith('confirmation.') ||
              event.type === 'evidence.linked' ||
              event.type === 'history.cleared'
            )
              setRevision((value) => value + 1);
          } catch {
            // Close without the ordinary reconnect path, then obtain an owned
            // snapshot. Do not guess across an event gap or changed authority.
            nextSocket.onclose = null;
            nextSocket.close();
            schedule(() => {
              void initialise();
            });
          }
        };
        nextSocket.onclose = () => {
          if (!disposed && socket === nextSocket) {
            setConnected(false);
            schedule(() => {
              void connect();
            });
          }
        };
        nextSocket.onerror = () => nextSocket.close();
      } catch {
        if (!disposed) {
          setConnected(false);
          schedule(() => {
            void connect();
          });
        }
      }
    };
    void initialise();
    return () => {
      disposed = true;
      clearTimeout(timer);
      socket?.close();
      setConnected(false);
    };
  }, [open, capabilities?.enabled, publish, reload]);

  const send = useCallback(async () => {
    if (
      !snapshot ||
      (!pending &&
        !(capabilities ?? snapshot.capabilities).accepting_messages) ||
      sendInFlight.current
    )
      return;
    const input: AcceptConversationMessage = pending ?? {
      client_message_id: createMessageId(),
      body: draft,
      origin: 'typed',
      reply_to_id: null,
    };
    if (!input.body.trim()) return;
    sendInFlight.current = true;
    setSending(true);
    setPending(input);
    setError(null);
    try {
      await supervisorApi.send(snapshot.conversation.id, input);
      setDraft('');
      setPending(null);
      setPage(null);
      // Only durable events populate history. Receipt success is not a second
      // assistant result, and a network retry reuses the same message identity.
    } catch (failure) {
      setError(String(failure));
    } finally {
      sendInFlight.current = false;
      setSending(false);
    }
  }, [snapshot, capabilities, pending, draft]);

  const earlier = useCallback(async () => {
    if (!snapshot || loading) return;
    const oldest = (page ?? history?.messages)?.[0]?.created_seq;
    if (oldest === undefined) return;
    setLoading(true);
    const epoch = dataEpoch.current;
    try {
      const messages = await supervisorApi.messages(
        snapshot.conversation.id,
        oldest
      );
      const runs = await supervisorApi.runs(snapshot.conversation.id, oldest);
      if (epoch !== dataEpoch.current) return;
      if (messages.length) {
        setPage(messages);
        setPageRuns(runs);
      }
      setHasEarlier(messages.length === 50);
    } catch (failure) {
      setError(String(failure));
    } finally {
      setLoading(false);
    }
  }, [snapshot, loading, page, history]);

  const context = useMemo(
    () => ({
      enabled: capabilities?.enabled === true,
      open,
      show: () => {
        launcher.current =
          document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null;
        // Recheck ownership and replay before exposing a cached transcript.
        // The draft stays local while navigation preserves this provider.
        setHistory(null);
        setSnapshot(null);
        setPage(null);
        setLoading(true);
        setOpen(true);
      },
    }),
    [capabilities?.enabled, open]
  );
  return (
    <SupervisorContext.Provider value={context}>
      {children}
      <SupervisorPanel
        open={open && capabilities?.enabled === true}
        onRestoreFocus={() => {
          const target = launcher.current?.isConnected
            ? launcher.current
            : document.querySelector<HTMLElement>(
                '[aria-controls="supervisor-dialog"]'
              );
          target?.focus();
        }}
        onClose={() => setOpen(false)}
        snapshot={
          snapshot && {
            ...snapshot,
            capabilities: capabilities ?? snapshot.capabilities,
          }
        }
        messages={page ?? history?.messages ?? []}
        runs={
          page
            ? mergeRuns(pageRuns, history?.runs ?? [])
            : (history?.runs ?? [])
        }
        loading={loading}
        connected={connected}
        error={error}
        draft={draft}
        onDraftChange={setDraft}
        onSend={() => {
          void send();
        }}
        sending={sending}
        retrying={pending !== null}
        onDiscardRetry={() => {
          setPending(null);
          setError(null);
        }}
        hasEarlier={hasEarlier}
        onEarlier={() => {
          void earlier();
        }}
        viewingEarlier={page !== null}
        onLatest={() => {
          setPage(null);
          setHasEarlier(true);
        }}
        activityRevision={revision}
        onReload={() => setReload((value) => value + 1)}
      />
    </SupervisorContext.Provider>
  );
}

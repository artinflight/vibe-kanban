import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@vibe/ui/components/Dialog';
import type {
  ConversationAction,
  ConversationEvidence,
  ConversationMemory,
  ConversationMessage,
  MessageEvidenceRef,
  SupervisorSnapshot,
  SupervisorRunStatus,
} from 'shared/types';
import { supervisorApi } from './api';
import { SupervisorConfirmations } from './SupervisorConfirmations';

const buttonClass =
  'rounded border border-border px-base py-half text-normal hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-50';

interface Props {
  open: boolean;
  onClose: () => void;
  onRestoreFocus: () => void;
  snapshot: SupervisorSnapshot | null;
  messages: ConversationMessage[];
  runs: SupervisorRunStatus[];
  loading: boolean;
  connected: boolean;
  error: string | null;
  draft: string;
  onDraftChange: (value: string) => void;
  onSend: () => void;
  sending: boolean;
  retrying: boolean;
  onDiscardRetry: () => void;
  hasEarlier: boolean;
  onEarlier: () => void;
  viewingEarlier: boolean;
  onLatest: () => void;
  activityRevision: number;
  onReload: () => void;
}

function ReplyStatus({ run }: { run: SupervisorRunStatus | undefined }) {
  const { t } = useTranslation('common');
  if (!run || run.status === 'completed') return null;
  const status = [
    'pending',
    'running',
    'failed',
    'interrupted',
    'cancelled',
  ].includes(run.status)
    ? run.status
    : 'failed';
  const reason =
    status === 'failed' &&
    [
      'model_authentication_failed',
      'model_rate_limited',
      'model_refused',
      'model_timeout',
      'worker_shutdown',
    ].includes(run.error ?? '')
      ? run.error
      : status;
  return (
    <p role="status" className="mt-half text-low">
      {t(`supervisor.replyState.${reason}`)}
    </p>
  );
}

function SourceDetails({
  conversationId,
  messageId,
  revision,
}: {
  conversationId: string;
  messageId: string;
  revision: number;
}) {
  const { t } = useTranslation('common');
  const [open, setOpen] = useState(false);
  const [sources, setSources] = useState<MessageEvidenceRef[]>([]);
  const [reports, setReports] = useState<ConversationEvidence[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    if (!open) return;
    let disposed = false;
    setLoading(true);
    setReports([]);
    setError(null);
    void supervisorApi
      .references(conversationId, messageId)
      .then(async (references) => {
        const evidence = await Promise.all(
          references.map((reference) =>
            supervisorApi.evidence(conversationId, reference.evidence_id)
          )
        );
        if (!disposed) {
          setSources(references);
          setReports(evidence);
        }
      })
      .catch((failure: unknown) => {
        if (!disposed) setError(String(failure));
      })
      .finally(() => {
        if (!disposed) setLoading(false);
      });
    return () => {
      disposed = true;
    };
  }, [open, conversationId, messageId, revision]);
  return (
    <details
      className="mt-half text-low"
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="cursor-pointer focus-visible:ring-2 focus-visible:ring-brand">
        {t('supervisor.sources')}
      </summary>
      {loading && <p>{t('supervisor.loading')}</p>}
      {error && (
        <p role="alert" className="text-error">
          {error}
        </p>
      )}
      {!loading && !error && reports.length === 0 && (
        <p>{t('supervisor.noSources')}</p>
      )}
      {reports.map((report, index) => (
        <details key={report.id} className="mt-base">
          <summary className="cursor-pointer">
            {t(
              report.source.kind === 'attention_snapshot'
                ? 'supervisor.attentionSnapshot'
                : 'supervisor.originalReport',
              { number: index + 1 }
            )}{' '}
            ·{' '}
            {t(
              `supervisor.relationship.${sources[index]?.relationship ?? 'supporting'}`
            )}
          </summary>
          <pre className="mt-half max-h-80 overflow-auto whitespace-pre-wrap break-words rounded bg-secondary p-base font-ibm-plex-mono text-normal">
            {report.raw_report ?? t('supervisor.sourceUnavailable')}
          </pre>
        </details>
      ))}
    </details>
  );
}

function SupervisorRecords({
  id,
  revision,
  onReload,
}: {
  id: string;
  revision: number;
  onReload: () => void;
}) {
  const { t } = useTranslation('common');
  const [actions, setActions] = useState<ConversationAction[]>([]);
  const [memories, setMemories] = useState<ConversationMemory[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let disposed = false;
    setActions([]);
    setMemories([]);
    setConfirmClear(null);
    void Promise.all([supervisorApi.actions(id), supervisorApi.memories(id)])
      .then(([activity, memory]) => {
        if (!disposed) {
          setActions(activity);
          setMemories(memory);
          setError(null);
        }
      })
      .catch((failure: unknown) => {
        if (!disposed) setError(String(failure));
      });
    return () => {
      disposed = true;
    };
  }, [id, revision, refresh]);
  const perform = async (work: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await work();
    } catch (failure) {
      setError(String(failure));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="space-y-base border-b border-border bg-secondary p-base">
      <details>
        <summary className="cursor-pointer text-high">
          {t('supervisor.activity')}
        </summary>
        {actions.length === 0 && (
          <p className="mt-half text-low">{t('supervisor.noActivity')}</p>
        )}
        {actions.map((action) => (
          <details key={action.id} className="mt-base">
            <summary className="cursor-pointer">
              {t('supervisor.instruction')} ·{' '}
              {t(`supervisor.state.${action.state}`)}
            </summary>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words p-half text-normal">
              {JSON.stringify(action.payload, null, 2)}
            </pre>
          </details>
        ))}
      </details>
      <details>
        <summary className="cursor-pointer text-high">
          {t('supervisor.preferences')}
        </summary>
        {memories.length === 0 && (
          <p className="mt-half text-low">{t('supervisor.noPreferences')}</p>
        )}
        {memories.map((memory) => (
          <div key={memory.id} className="my-base space-y-half">
            <p className="text-normal">{memory.body}</p>
            <p className="text-low">
              {t(`supervisor.scope.${memory.scope_kind}`)} ·{' '}
              {t(`supervisor.state.${memory.state}`)}
            </p>
            <button
              className={buttonClass}
              disabled={busy}
              onClick={() => {
                void perform(async () => {
                  await supervisorApi.forget(id, memory);
                  setRefresh((value) => value + 1);
                });
              }}
            >
              {t('supervisor.forget')}
            </button>
          </div>
        ))}
      </details>
      <div className="flex flex-wrap gap-base">
        <button
          className={buttonClass}
          disabled={busy}
          onClick={() => {
            void perform(async () => {
              const data = await supervisorApi.export(id);
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(data, null, 2)], {
                  type: 'application/json',
                })
              );
              const link = document.createElement('a');
              link.href = url;
              link.download = 'vk-supervisor-history.json';
              link.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            });
          }}
        >
          {t('supervisor.export')}
        </button>
        <button
          className={buttonClass}
          disabled={busy}
          onClick={() => {
            void perform(async () => {
              setConfirmClear(
                (await supervisorApi.snapshot(id)).conversation.revision
              );
            });
          }}
        >
          {t('supervisor.clear')}
        </button>
      </div>
      {confirmClear !== null && (
        <div className="space-y-half rounded border border-border p-base">
          <p>{t('supervisor.clearExplanation')}</p>
          <button
            className={buttonClass}
            disabled={busy}
            onClick={() => {
              void perform(async () => {
                await supervisorApi.clear(id, confirmClear);
                setConfirmClear(null);
                onReload();
              });
            }}
          >
            {t('supervisor.confirmClear')}
          </button>
          <button
            className={buttonClass}
            disabled={busy}
            onClick={() => setConfirmClear(null)}
          >
            {t('supervisor.cancel')}
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-error">
          {error}
        </p>
      )}
    </section>
  );
}

export function SupervisorPanel(props: Props) {
  const { t } = useTranslation('common');
  const [settings, setSettings] = useState(false);
  const scroll = useRef<HTMLDivElement>(null);
  const nearBottom = useRef(true);
  const lastMessage = props.messages.at(-1);
  useEffect(() => {
    if (nearBottom.current && !props.viewingEarlier)
      scroll.current?.scrollTo({ top: scroll.current.scrollHeight });
  }, [lastMessage?.id, props.viewingEarlier, props.open]);
  const ready = !!props.snapshot?.capabilities.accepting_messages;
  return (
    <Dialog
      open={props.open}
      onOpenChange={(open) => {
        if (!open) props.onClose();
      }}
    >
      <DialogContent
        id="supervisor-dialog"
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          props.onRestoreFocus();
        }}
        className="new-design left-auto right-0 top-0 flex h-dvh w-full max-w-lg translate-x-0 translate-y-0 flex-col rounded-none bg-primary p-0 text-base text-normal"
        aria-describedby="supervisor-description"
      >
        <header className="shrink-0 border-b border-border p-base pr-10">
          <DialogTitle>{t('supervisor.title')}</DialogTitle>
          <DialogDescription id="supervisor-description">
            {t('supervisor.authority')}
          </DialogDescription>
          <div className="mt-half flex items-center gap-base">
            <span className="text-low" role="status">
              {props.connected
                ? t('supervisor.connected')
                : t('supervisor.reconnecting')}
            </span>
            <button
              className={buttonClass}
              onClick={() => setSettings((value) => !value)}
              aria-expanded={settings}
            >
              {t('supervisor.details')}
            </button>
          </div>
        </header>
        {settings && props.snapshot && (
          <div className="max-h-[40vh] shrink-0 overflow-auto">
            <SupervisorRecords
              id={props.snapshot.conversation.id}
              revision={props.activityRevision}
              onReload={props.onReload}
            />
          </div>
        )}
        <div
          ref={scroll}
          className="min-h-0 flex-1 overflow-y-auto p-base"
          onScroll={(event) => {
            const node = event.currentTarget;
            nearBottom.current =
              node.scrollHeight - node.scrollTop - node.clientHeight < 80;
          }}
        >
          <div className="mb-base flex gap-base">
            {props.hasEarlier && props.messages.length > 0 && (
              <button
                className={buttonClass}
                disabled={props.loading}
                onClick={props.onEarlier}
              >
                {t('supervisor.earlier')}
              </button>
            )}
            {props.viewingEarlier && (
              <button className={buttonClass} onClick={props.onLatest}>
                {t('supervisor.latest')}
              </button>
            )}
          </div>
          {props.loading && <p role="status">{t('supervisor.loading')}</p>}
          {!props.loading && props.messages.length === 0 && (
            <p className="text-low">{t('supervisor.empty')}</p>
          )}
          {props.snapshot && !props.viewingEarlier && (
            <SupervisorConfirmations
              key={props.snapshot.conversation.id}
              id={props.snapshot.conversation.id}
              revision={props.activityRevision}
              available={props.snapshot.capabilities.agent_actions}
            />
          )}
          <ol className="space-y-double" aria-label={t('supervisor.history')}>
            {props.messages.map((message) => (
              <li
                key={message.id}
                className={
                  message.role === 'user'
                    ? 'ml-double rounded bg-secondary p-base'
                    : 'mr-base'
                }
              >
                <p className="mb-half text-low">
                  {message.role === 'user'
                    ? t('supervisor.you')
                    : t('supervisor.title')}
                </p>
                <p className="whitespace-pre-wrap break-words text-normal">
                  {message.body}
                </p>
                {message.role === 'user' && (
                  <ReplyStatus
                    run={props.runs.find(
                      (run) => run.input_message_id === message.id
                    )}
                  />
                )}
                {message.role === 'assistant' && props.snapshot && (
                  <SourceDetails
                    conversationId={props.snapshot.conversation.id}
                    messageId={message.id}
                    revision={props.activityRevision}
                  />
                )}
              </li>
            ))}
          </ol>
        </div>
        <p className="sr-only" aria-live="polite" aria-atomic="true">
          {lastMessage?.role === 'assistant' && !props.viewingEarlier ? (
            <span key={lastMessage.id}>{t('supervisor.newReply')}</span>
          ) : null}
        </p>
        <form
          className="shrink-0 space-y-half border-t border-border p-base pb-[max(12px,env(safe-area-inset-bottom))]"
          onSubmit={(event) => {
            event.preventDefault();
            props.onSend();
          }}
        >
          {!ready && (
            <p className="text-low">{t('supervisor.modelUnavailable')}</p>
          )}
          {props.error && (
            <div role="alert" className="text-error">
              <p>{props.error}</p>
              <button
                type="button"
                className={buttonClass}
                onClick={props.onReload}
              >
                {t('supervisor.reload')}
              </button>
            </div>
          )}
          <label htmlFor="supervisor-input" className="sr-only">
            {t('supervisor.message')}
          </label>
          <textarea
            id="supervisor-input"
            className="min-h-20 w-full resize-y rounded border border-border bg-secondary p-base text-normal placeholder:text-low focus:outline-none focus:ring-2 focus:ring-brand"
            value={props.draft}
            onChange={(event) => props.onDraftChange(event.target.value)}
            readOnly={props.retrying || props.sending}
            disabled={!ready}
            maxLength={16000}
            placeholder={t('supervisor.placeholder')}
          />
          <div className="flex flex-wrap items-center justify-end gap-base">
            {props.retrying && !props.sending && (
              <button
                type="button"
                className={buttonClass}
                onClick={props.onDiscardRetry}
              >
                {t('supervisor.editNew')}
              </button>
            )}
            <button
              type="submit"
              className={buttonClass}
              disabled={
                (!ready && !props.retrying) ||
                !props.snapshot ||
                props.sending ||
                !props.draft.trim()
              }
            >
              {props.sending
                ? t('supervisor.sending')
                : props.retrying
                  ? t('supervisor.retry')
                  : t('supervisor.send')}
            </button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

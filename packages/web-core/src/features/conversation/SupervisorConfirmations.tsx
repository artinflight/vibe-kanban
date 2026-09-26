import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ActionConfirmation, SupervisorActionDetail } from 'shared/types';
import { supervisorApi } from './api';

const buttonClass =
  'rounded border border-border px-base py-half focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-50';
interface Review {
  confirmation: ActionConfirmation;
  detail: SupervisorActionDetail;
}
export function SupervisorConfirmations({
  id,
  revision,
  available,
}: {
  id: string;
  revision: number;
  available: boolean;
}) {
  const { t } = useTranslation('common');
  const [reviews, setReviews] = useState<Review[]>([]);
  const [refresh, setRefresh] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  useEffect(() => {
    let disposed = false;
    void supervisorApi
      .confirmations(id)
      .then(async (confirmations) => {
        const results = await Promise.all(
          confirmations
            .filter((c) => c.state === 'pending' || c.state === 'accepted')
            .map(async (confirmation) => ({
              confirmation,
              detail: await supervisorApi.action(id, confirmation.action_id),
            }))
        );
        if (!disposed)
          setReviews(
            results.filter(
              (r) =>
                r.detail.action.state === 'proposed' ||
                r.detail.action.state === 'approved'
            )
          );
      })
      .catch((failure: unknown) => {
        if (!disposed) setError(String(failure));
      });
    return () => {
      disposed = true;
    };
  }, [id, revision, refresh]);
  useEffect(() => {
    if (reviews.length === 0) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [reviews.length]);
  async function answer(review: Review, accept: boolean) {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      const result = await supervisorApi.confirm(id, review.confirmation.id, {
        accept,
        payload_digest: review.confirmation.payload_digest,
        action_revision: review.confirmation.action_revision,
      });
      setStatus(
        result.blocked
          ? t('supervisor.confirmation.blocked')
          : t('supervisor.confirmation.sent')
      );
      setRefresh((value) => value + 1);
    } catch (failure) {
      setError(String(failure));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="mb-base space-y-base"
      aria-label={t('supervisor.confirmation.title')}
    >
      {reviews.map((review) => {
        const { confirmation: c, detail } = review;
        const expired = c.expires_at * 1000 <= now;
        const intact =
          !!detail.message &&
          detail.action.payload_digest === c.payload_digest &&
          (c.state === 'accepted' ||
            detail.action.revision === c.action_revision);
        return (
          <article
            key={c.id}
            className="space-y-base rounded border border-border p-base"
          >
            <h3 className="font-semibold">
              {t('supervisor.confirmation.title')}
            </h3>
            <p className="whitespace-pre-wrap break-words">
              {detail.message?.message}
            </p>
            <p>{t('supervisor.confirmation.recipients')}</p>
            <ul className="space-y-half">
              {detail.message?.targets.map((target) => (
                <li key={target.session_id}>
                  <a
                    href={`/workspaces/${target.workspace_id}`}
                    className="underline"
                    title={target.session_id}
                  >
                    {target.workspace_name} ·{' '}
                    {target.session_name ?? target.branch}
                  </a>{' '}
                  <span className="text-low">({target.branch})</span>
                </li>
              ))}
            </ul>
            {detail.blocked && (
              <p role="status">
                {t(`supervisor.confirmation.block.${detail.blocked}`, {
                  defaultValue: t('supervisor.confirmation.blocked'),
                })}
              </p>
            )}
            {expired && <p>{t('supervisor.confirmation.expired')}</p>}
            {!intact && <p>{t('supervisor.confirmation.invalid')}</p>}
            {!available && <p>{t('supervisor.confirmation.unavailable')}</p>}
            <div className="flex gap-base">
              <button
                className={buttonClass}
                disabled={busy || expired || !intact || !available}
                onClick={() => {
                  void answer(review, true);
                }}
              >
                {t(
                  c.state === 'accepted'
                    ? 'supervisor.confirmation.retry'
                    : 'supervisor.confirmation.send'
                )}
              </button>
              {c.state === 'pending' && (
                <button
                  className={buttonClass}
                  disabled={busy || expired}
                  onClick={() => {
                    void answer(review, false);
                  }}
                >
                  {t('supervisor.confirmation.reject')}
                </button>
              )}
            </div>
          </article>
        );
      })}
      {error && (
        <p role="alert" className="text-error">
          {error}
        </p>
      )}
      {status && <p role="status">{status}</p>}
    </section>
  );
}

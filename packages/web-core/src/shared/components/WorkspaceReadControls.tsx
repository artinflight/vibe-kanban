import { useRef, useState } from 'react';
import { useWorkspaceSeenAction } from '@/shared/hooks/useWorkspaceSeenAction';

/** The existing read API clears all sessions, so this must stay explicit. */
export function WorkspaceReadControls({
  workspaceId,
}: {
  workspaceId: string;
}) {
  const markSeen = useWorkspaceSeenAction();
  const inFlight = useRef(false);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  const markRead = async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setFailed(false);
    try {
      await markSeen(workspaceId);
    } catch {
      setFailed(true);
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  };

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-end gap-base border-b border-border px-base py-half">
      {failed && (
        <span role="alert" className="text-sm text-error">
          Could not mark replies read. Try again.
        </span>
      )}
      <button
        type="button"
        disabled={pending}
        onClick={(event) => {
          event.stopPropagation();
          void markRead();
        }}
        title="Mark all agent replies in this workspace, across all sessions, as read"
        className="rounded-sm px-base py-half text-base text-normal hover:bg-secondary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand disabled:cursor-wait disabled:opacity-50"
      >
        {pending ? 'Marking replies read…' : 'Mark all replies read'}
      </button>
    </div>
  );
}

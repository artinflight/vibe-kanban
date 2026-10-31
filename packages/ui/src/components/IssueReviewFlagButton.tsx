import type { MouseEvent } from 'react';
import { FlagIcon } from '@phosphor-icons/react';
import { cn } from '../lib/cn';

/** An explicit issue flag, independent of whether workspace replies are unread. */
export function IssueReviewFlagButton({
  flagged,
  onToggle,
  showLabel = false,
  displayId,
}: {
  flagged: boolean;
  onToggle: (event: MouseEvent) => void;
  showLabel?: boolean;
  displayId?: string;
}) {
  const action = flagged ? 'Clear review flag' : 'Add review flag';
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onToggle(event);
      }}
      onMouseDown={(event) => event.stopPropagation()}
      className={cn(
        'flex shrink-0 items-center gap-half rounded-sm p-half transition-colors hover:bg-secondary',
        flagged ? 'text-brand' : 'text-low hover:text-normal',
        showLabel && 'min-h-12'
      )}
      aria-pressed={flagged}
      aria-label={displayId ? `${action} for ${displayId}` : action}
      title={action}
    >
      <FlagIcon
        className="size-icon-xs"
        weight={flagged ? 'fill' : 'regular'}
      />
      {showLabel && (
        <span className="text-sm">
          {flagged ? 'Flagged for review · Clear' : 'Flag for review'}
        </span>
      )}
    </button>
  );
}

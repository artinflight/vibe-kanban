import {
  DotActivityIndicators,
  type DotActivityState,
} from './DotActivityIndicators';
import {
  PushPinIcon,
  HandIcon,
  TriangleIcon,
  PlayIcon,
  FileIcon,
  CircleIcon,
  GitPullRequestIcon,
  DotsThreeIcon,
  StackIcon,
} from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { usePhoneLayout } from '../lib/usePhoneLayout';
import { cn } from '../lib/cn';
import { ReadLaterButton } from './ReadLaterButton';
import { RunningDots } from './RunningDots';
import { DotManagedIndicator } from './DotManagedIndicator';

const formatRelativeElapsed = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
};

export interface WorkspaceSummaryProps extends DotActivityState {
  name: string;
  workspaceId?: string;
  dotManaged?: boolean;
  filesChanged?: number;
  linesAdded?: number;
  linesRemoved?: number;
  isActive?: boolean;
  isRunning?: boolean;
  isPinned?: boolean;
  hasPendingApproval?: boolean;
  hasRunningDevServer?: boolean;
  hasUnseenActivity?: boolean;
  activeSubagentCount?: number;
  unresolvedSubagentCount?: number;
  latestProcessCompletedAt?: string;
  latestProcessStatus?: 'running' | 'completed' | 'failed' | 'killed';
  prStatus?: 'open' | 'merged' | 'closed' | 'unknown';
  onClick?: () => void;
  className?: string;
  summary?: boolean;
  /** Whether this is a draft workspace (shows "Draft" instead of elapsed time) */
  isDraft?: boolean;
  readLater?: boolean;
  onToggleReadLater?: () => void;
  onOpenWorkspaceActions?: (workspaceId: string) => void;
}

export function WorkspaceSummary({
  name,
  workspaceId,
  filesChanged,
  linesAdded,
  linesRemoved,
  isActive = false,
  isRunning = false,
  isPinned = false,
  hasPendingApproval = false,
  hasRunningDevServer = false,
  hasUnseenActivity = false,
  dotManaged = false,
  dotUnreadCount = 0,
  dotNeedsAttentionCount = 0,
  activeSubagentCount = 0,
  unresolvedSubagentCount = 0,
  latestProcessCompletedAt,
  latestProcessStatus,
  prStatus,
  onClick,
  className,
  summary = false,
  isDraft = false,
  onOpenWorkspaceActions,
  readLater,
  onToggleReadLater,
}: WorkspaceSummaryProps) {
  const { t } = useTranslation('common');
  const phone = usePhoneLayout();
  const hasChanges = filesChanged !== undefined && filesChanged > 0;
  const hasDotActivity = dotUnreadCount > 0 || dotNeedsAttentionCount > 0;
  const isFailed =
    latestProcessStatus === 'failed' || latestProcessStatus === 'killed';
  const subagentCount = activeSubagentCount + unresolvedSubagentCount;
  const hasSubagentActivity = subagentCount > 0;
  const showMetadata =
    !summary ||
    isActive ||
    hasDotActivity ||
    dotManaged ||
    !!onToggleReadLater ||
    !!(workspaceId && onOpenWorkspaceActions);

  const handleOpenCommandBar = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!workspaceId || !onOpenWorkspaceActions) return;
    onOpenWorkspaceActions(workspaceId);
  };

  if (phone) {
    const attention =
      hasPendingApproval ||
      (hasUnseenActivity && !isRunning && !hasSubagentActivity);
    const state = isDraft
      ? 'Draft'
      : hasPendingApproval
        ? 'Approval needed'
        : isRunning || hasSubagentActivity
          ? 'Running'
          : isFailed
            ? 'Failed'
            : hasUnseenActivity
              ? 'New activity'
              : 'Ready';
    return (
      <article
        className={cn(
          'mobile-workspace-card phone-workspace-row !block',
          className
        )}
        data-selected={isActive}
      >
        <button
          type="button"
          data-workspace-title
          className="phone-workspace-open w-full !pb-0"
          aria-current={isActive ? 'page' : undefined}
          onClick={onClick}
        >
          <span
            className={cn(
              'phone-workspace-symbol',
              attention && 'phone-attention',
              isRunning && 'phone-running'
            )}
          >
            {attention ? (
              <HandIcon size={22} />
            ) : isRunning || hasSubagentActivity ? (
              <PlayIcon size={22} weight="fill" />
            ) : isFailed ? (
              <TriangleIcon size={22} />
            ) : (
              <StackIcon size={22} />
            )}
          </span>
          <span className="phone-workspace-text">
            <span className="phone-workspace-name">
              {isPinned && <PushPinIcon size={14} weight="fill" />}
              {name}
            </span>
          </span>
        </button>
        <div
          data-workspace-status-row
          className="flex items-center gap-half pb-half pl-[52px]"
        >
          <button
            type="button"
            onClick={onClick}
            aria-label={name}
            className="min-w-0 flex-1 text-left"
          >
            <span className="phone-workspace-caption">
              <span>{state}</span>
              <DotManagedIndicator managed={dotManaged} />
              <DotActivityIndicators
                dotUnreadCount={dotUnreadCount}
                dotNeedsAttentionCount={dotNeedsAttentionCount}
              />
              {latestProcessCompletedAt && !isRunning && (
                <> · {formatRelativeElapsed(latestProcessCompletedAt)}</>
              )}
              {hasChanges && <> · {filesChanged} files</>}
              {hasSubagentActivity && <> · {subagentCount} agents</>}
              {hasRunningDevServer && <> · Preview running</>}
              {prStatus && prStatus !== 'unknown' && <> · PR {prStatus}</>}
            </span>
          </button>
          {onToggleReadLater && (
            <ReadLaterButton later={readLater} onToggle={onToggleReadLater} />
          )}
          {workspaceId && onOpenWorkspaceActions && (
            <button
              type="button"
              className="phone-row-more inline-flex size-11 shrink-0 items-center justify-center"
              aria-label={`Actions for ${name}`}
              onClick={handleOpenCommandBar}
            >
              <DotsThreeIcon size={22} weight="bold" />
            </button>
          )}
        </div>
      </article>
    );
  }

  return (
    <div
      className={cn(
        'mobile-workspace-card group relative rounded-sm transition-all duration-100 overflow-hidden',
        isActive ? 'bg-tertiary' : '',
        className
      )}
    >
      {/* Selection indicator - thin colored tab on the left */}
      <div
        className={cn(
          'absolute left-0 top-1 bottom-1 w-0.5 rounded-full transition-colors duration-100',
          isActive ? 'bg-brand' : 'bg-transparent'
        )}
      />
      <button
        type="button"
        data-workspace-title
        aria-current={isActive ? 'page' : undefined}
        onClick={onClick}
        className={cn(
          'flex w-full min-w-0 cursor-pointer flex-col text-left px-base pt-half transition-all duration-150 text-normal',
          !showMetadata && 'pb-half'
        )}
      >
        <div
          className={cn(
            'w-full overflow-hidden whitespace-nowrap',
            !summary && 'text-normal'
          )}
          style={{
            maskImage:
              'linear-gradient(to right, black calc(100% - 24px), transparent 100%)',
            WebkitMaskImage:
              'linear-gradient(to right, black calc(100% - 24px), transparent 100%)',
          }}
        >
          {name}
        </div>
      </button>
      {showMetadata && (
        <div
          data-workspace-status-row
          className="flex w-full items-center px-base pb-half"
        >
          <button
            type="button"
            onClick={onClick}
            aria-label={name}
            className="min-w-0 flex-1 cursor-pointer text-left text-normal"
          >
            <div
              className={cn(
                'flex w-full items-center gap-base text-sm',
                hasDotActivity || dotManaged ? 'flex-wrap min-h-5' : 'h-5'
              )}
            >
              {/* Dev server running - leftmost */}
              {hasRunningDevServer && (
                <PlayIcon
                  className="size-icon-xs text-brand shrink-0"
                  weight="fill"
                />
              )}

              {/* Failed/killed status (only when not running) */}
              {!isRunning && isFailed && (
                <TriangleIcon
                  className="size-icon-xs text-error shrink-0"
                  weight="fill"
                />
              )}

              {/* Approval remains visible independently of running activity. */}
              {hasPendingApproval ? (
                <HandIcon
                  className="size-icon-xs text-brand shrink-0"
                  weight="fill"
                  role="img"
                  aria-label="Pending approval"
                />
              ) : isRunning ? (
                <RunningDots />
              ) : null}

              {/* Unseen activity indicator (only when not running and not failed) */}
              {hasUnseenActivity &&
                !isRunning &&
                !hasSubagentActivity &&
                !isFailed && (
                  <CircleIcon
                    className="size-icon-xs text-brand shrink-0"
                    weight="fill"
                  />
                )}

              <DotManagedIndicator managed={dotManaged} />
              <DotActivityIndicators
                dotUnreadCount={dotUnreadCount}
                dotNeedsAttentionCount={dotNeedsAttentionCount}
              />
              {/* Sub-agent activity from the Codex thread graph */}
              {hasSubagentActivity && (
                <span
                  className="inline-flex h-4 min-w-4 shrink-0 items-center gap-[2px] text-warning"
                  title={`${subagentCount} sub-agent${
                    subagentCount === 1 ? '' : 's'
                  } active`}
                >
                  <StackIcon className="size-icon-xs" weight="fill" />
                  {subagentCount > 1 && (
                    <span className="text-[10px] leading-none tabular-nums">
                      {subagentCount}
                    </span>
                  )}
                </span>
              )}

              {/* PR status icon */}
              {prStatus === 'open' && (
                <GitPullRequestIcon
                  className="size-icon-xs text-success shrink-0"
                  weight="fill"
                />
              )}
              {prStatus === 'merged' && (
                <GitPullRequestIcon
                  className="size-icon-xs text-merged shrink-0"
                  weight="fill"
                />
              )}

              {/* Pin icon */}
              {isPinned && (
                <PushPinIcon
                  className="size-icon-xs text-brand shrink-0"
                  weight="fill"
                />
              )}

              {/* Time elapsed OR "Draft" label (when not running) */}
              {!isRunning &&
                !hasSubagentActivity &&
                (isDraft ? (
                  <span className="min-w-0 flex-1 truncate">
                    {t('workspaces.draft')}
                  </span>
                ) : latestProcessCompletedAt ? (
                  <span className="min-w-0 flex-1 truncate">
                    {formatRelativeElapsed(latestProcessCompletedAt)}
                  </span>
                ) : (
                  <span className="flex-1" />
                ))}

              {/* Spacer when running (no elapsed time shown) */}
              {(isRunning || hasSubagentActivity) && (
                <span className="flex-1" />
              )}

              {/* File count + lines changed on the right */}
              {hasChanges && (
                <span className="shrink-0 text-right flex items-center gap-half">
                  <FileIcon className="size-icon-xs" weight="fill" />
                  <span>{filesChanged}</span>
                  {linesAdded !== undefined && (
                    <span className="text-success">+{linesAdded}</span>
                  )}
                  {linesRemoved !== undefined && (
                    <span className="text-error">-{linesRemoved}</span>
                  )}
                </span>
              )}
            </div>
          </button>

          <div className="flex shrink-0 items-center pr-half">
            {onToggleReadLater && (
              <ReadLaterButton later={readLater} onToggle={onToggleReadLater} />
            )}
            {workspaceId && onOpenWorkspaceActions && (
              <button
                type="button"
                onClick={handleOpenCommandBar}
                onPointerDown={(event) => event.stopPropagation()}
                className="rounded-sm p-1.5 text-low hover:bg-tertiary hover:text-normal focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand sm:opacity-0 sm:group-hover:opacity-100 sm:focus-visible:opacity-100"
                aria-label={t('workspaces.more')}
                title={t('workspaces.more')}
              >
                <DotsThreeIcon className="size-5" weight="bold" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

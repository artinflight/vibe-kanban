import { cn } from '../lib/cn';
import { useTranslation } from 'react-i18next';
import {
  GitPullRequestIcon,
  DotsThreeIcon,
  LinkBreakIcon,
  PencilSimpleIcon,
  TrashIcon,
  ArchiveIcon,
  PlayIcon,
  HandIcon,
  TriangleIcon,
  CircleIcon,
  PaletteIcon,
} from '@phosphor-icons/react';
import { UserAvatar, type UserAvatarUser } from './UserAvatar';
import { RunningDots } from './RunningDots';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from './DropdownMenu';

export const WORKSPACE_COLORS = [
  '6 78% 84%',
  '28 92% 82%',
  '45 95% 78%',
  '84 64% 80%',
  '145 55% 78%',
  '174 58% 78%',
  '202 82% 82%',
  '232 72% 84%',
  '262 70% 86%',
  '302 62% 85%',
  '334 78% 84%',
  '358 74% 84%',
] as const;

export interface WorkspacePr {
  number: number;
  url: string;
  status: 'open' | 'merged' | 'closed';
}

export interface WorkspaceWithStats {
  id: string;
  localWorkspaceId: string | null;
  name: string | null;
  archived: boolean;
  filesChanged: number;
  linesAdded: number;
  linesRemoved: number;
  prs: WorkspacePr[];
  owner: UserAvatarUser | null;
  updatedAt: string;
  isOwnedByCurrentUser: boolean;
  isRunning?: boolean;
  hasPendingApproval?: boolean;
  hasRunningDevServer?: boolean;
  hasUnseenActivity?: boolean;
  latestProcessCompletedAt?: string;
  latestProcessStatus?: 'running' | 'completed' | 'failed' | 'killed';
}

export interface IssueWorkspaceCardProps {
  workspace: WorkspaceWithStats;
  onClick?: () => void;
  onRename?: () => void;
  onArchive?: () => void;
  onUnlink?: () => void;
  onDelete?: () => void;
  color?: string;
  onColorChange?: (color: string | null) => void;
  showOwner?: boolean;
  showStatusBadge?: boolean;
  showNoPrText?: boolean;
  className?: string;
}

export interface IssueWorkspaceCreateCardProps {
  onClick?: () => void;
  className?: string;
  shouldAnimateCreateButton?: boolean;
}

interface IssueWorkspaceCardContainerProps {
  onClick?: () => void;
  className?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

function IssueWorkspaceCardContainer({
  onClick,
  className,
  children,
  style,
}: IssueWorkspaceCardContainerProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-half p-base bg-panel rounded-sm transition-all duration-150',
        onClick && 'cursor-pointer hover:bg-secondary/70',
        className
      )}
      style={style}
      onClick={
        onClick
          ? (e) => {
              e.stopPropagation();
              onClick();
            }
          : undefined
      }
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();
                onClick();
              }
            }
          : undefined
      }
    >
      {children}
    </div>
  );
}

export function IssueWorkspaceCard({
  workspace,
  onClick,
  onRename,
  onArchive,
  onUnlink,
  onDelete,
  color,
  onColorChange,
  showOwner = true,
  showStatusBadge = true,
  showNoPrText = true,
  className,
}: IssueWorkspaceCardProps) {
  const { t } = useTranslation('common');
  const timeAgo = getTimeAgo(
    workspace.latestProcessCompletedAt ?? workspace.updatedAt
  );
  const isRunning = workspace.isRunning ?? false;
  const hasPendingApproval = workspace.hasPendingApproval ?? false;
  const hasRunningDevServer = workspace.hasRunningDevServer ?? false;
  const hasUnseenActivity = workspace.hasUnseenActivity ?? false;
  const isFailed =
    workspace.latestProcessStatus === 'failed' ||
    workspace.latestProcessStatus === 'killed';
  const hasLiveStatusIndicator =
    hasRunningDevServer ||
    isFailed ||
    isRunning ||
    (hasUnseenActivity && !isRunning);
  const shouldStackPrBadges = workspace.prs.length > 2;

  return (
    <IssueWorkspaceCardContainer
      onClick={onClick}
      className={cn(
        color &&
          'bg-[hsl(var(--workspace-color)/0.48)] shadow-[inset_3px_0_0_hsl(var(--workspace-color)/0.85)] dark:bg-[hsl(var(--workspace-color)/0.18)]',
        className
      )}
      style={
        color
          ? ({ '--workspace-color': color } as React.CSSProperties)
          : undefined
      }
    >
      {/* Row 1: Status badge + Name (left), Owner avatar + menu (right) */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-half min-w-0">
          {showStatusBadge && (
            <span
              className={cn(
                'px-1.5 py-0.5 rounded text-xs font-medium shrink-0',
                workspace.archived
                  ? 'bg-secondary text-low'
                  : 'bg-success/10 text-success'
              )}
            >
              {workspace.archived
                ? t('workspaces.archived')
                : t('workspaces.active')}
            </span>
          )}
          {workspace.name && (
            <span className="text-sm text-high truncate">{workspace.name}</span>
          )}
        </div>

        <div className="flex items-center gap-half">
          {showOwner && workspace.owner && (
            <UserAvatar
              user={workspace.owner}
              className="h-5 w-5 text-[10px] border-2 border-panel"
            />
          )}
          {(onColorChange || onRename || onArchive || onUnlink || onDelete) && (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  onClick={(e) => e.stopPropagation()}
                  className="p-0.5 rounded hover:bg-secondary transition-colors"
                  aria-label={t('workspaces.more')}
                >
                  <DotsThreeIcon
                    className="size-icon-xs text-low"
                    weight="bold"
                  />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {onColorChange && (
                  <DropdownMenuSub>
                    <DropdownMenuSubTrigger
                      onClick={(e) => e.stopPropagation()}
                    >
                      <PaletteIcon className="size-icon-xs" />
                      {t('workspaces.color', { defaultValue: 'Color' })}
                    </DropdownMenuSubTrigger>
                    <DropdownMenuSubContent className="w-40 p-base">
                      <div className="grid grid-cols-4 gap-half">
                        {WORKSPACE_COLORS.map((workspaceColor) => (
                          <button
                            key={workspaceColor}
                            type="button"
                            aria-label={t('workspaces.setColor', {
                              defaultValue: 'Set workspace color',
                            })}
                            onClick={(e) => {
                              e.stopPropagation();
                              onColorChange(workspaceColor);
                            }}
                            className={cn(
                              'size-6 rounded-full border border-black/15 hover:scale-110 transition-transform dark:border-white/20',
                              color === workspaceColor &&
                                'ring-2 ring-brand ring-offset-1 ring-offset-primary'
                            )}
                            style={{ backgroundColor: `hsl(${workspaceColor})` }}
                          />
                        ))}
                      </div>
                      {color && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onColorChange(null);
                          }}
                          className="mt-base w-full text-left text-sm text-low hover:text-normal"
                        >
                          {t('workspaces.clearColor', {
                            defaultValue: 'Clear color',
                          })}
                        </button>
                      )}
                    </DropdownMenuSubContent>
                  </DropdownMenuSub>
                )}
                {onRename && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onRename();
                    }}
                  >
                    <PencilSimpleIcon className="size-icon-xs" />
                    {t('workspaces.rename.action')}
                  </DropdownMenuItem>
                )}
                {onArchive && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onArchive();
                    }}
                  >
                    <ArchiveIcon className="size-icon-xs" />
                    {workspace.archived
                      ? t('workspaces.unarchive', {
                          defaultValue: 'Unarchive',
                        })
                      : t('workspaces.archive')}
                  </DropdownMenuItem>
                )}
                {onUnlink && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onUnlink();
                    }}
                  >
                    <LinkBreakIcon className="size-icon-xs" />
                    {t('workspaces.unlinkFromIssue')}
                  </DropdownMenuItem>
                )}
                {onDelete && (
                  <DropdownMenuItem
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete();
                    }}
                    className="text-destructive focus:text-destructive"
                  >
                    <TrashIcon className="size-icon-xs" />
                    {t('workspaces.deleteWorkspace')}
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>

      {/* Row 2: Live status + stats, with many PRs wrapped underneath. */}
      <div
        className={cn(
          'flex gap-half min-w-0',
          shouldStackPrBadges
            ? 'flex-col items-start'
            : 'items-center justify-between'
        )}
      >
        <div
          className={cn(
            'flex items-center flex-wrap sm:flex-nowrap gap-half text-sm text-low min-w-0 overflow-hidden',
            shouldStackPrBadges ? 'w-full' : 'flex-1'
          )}
        >
          <div className="flex items-center gap-half shrink-0">
            {hasRunningDevServer && (
              <PlayIcon
                className="size-icon-xs text-brand shrink-0"
                weight="fill"
              />
            )}

            {!isRunning && isFailed && (
              <TriangleIcon
                className="size-icon-xs text-error shrink-0"
                weight="fill"
              />
            )}

            {isRunning &&
              (hasPendingApproval ? (
                <HandIcon
                  className="size-icon-xs text-brand shrink-0"
                  weight="fill"
                />
              ) : (
                <RunningDots />
              ))}

            {hasUnseenActivity && !isRunning && !isFailed && (
              <CircleIcon
                className="size-icon-xs text-brand shrink-0"
                weight="fill"
              />
            )}
          </div>

          {hasLiveStatusIndicator && (
            <span className="text-low/50 shrink-0">·</span>
          )}

          <span className="whitespace-nowrap shrink-0">{timeAgo}</span>
          {workspace.filesChanged > 0 && (
            <>
              <span className="text-low/50 shrink-0">·</span>
              <span className="whitespace-nowrap shrink-0">
                {t('workspaces.filesChanged', {
                  count: workspace.filesChanged,
                })}
              </span>
            </>
          )}
          {workspace.linesAdded > 0 && (
            <>
              <span className="text-low/50 shrink-0">·</span>
              <span className="text-success whitespace-nowrap shrink-0">
                +{workspace.linesAdded}
              </span>
            </>
          )}
          {workspace.linesRemoved > 0 && (
            <>
              <span className="text-low/50 shrink-0">·</span>
              <span className="text-error whitespace-nowrap shrink-0">
                -{workspace.linesRemoved}
              </span>
            </>
          )}
        </div>

        <div
          className={cn(
            'flex items-center gap-half flex-wrap max-w-full',
            shouldStackPrBadges ? 'justify-start' : 'justify-end shrink-0'
          )}
        >
          {workspace.prs.length > 0 ? (
            workspace.prs.map((pr) => (
              <a
                key={pr.number}
                href={pr.url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className={cn(
                  'flex items-center gap-half px-1.5 py-0.5 rounded text-xs font-medium transition-colors',
                  pr.status === 'merged'
                    ? 'bg-merged/10 text-merged hover:bg-merged/20'
                    : pr.status === 'closed'
                      ? 'bg-error/10 text-error hover:bg-error/20'
                      : 'bg-success/10 text-success hover:bg-success/20'
                )}
              >
                <GitPullRequestIcon className="size-icon-2xs" weight="bold" />
                <span>#{pr.number}</span>
              </a>
            ))
          ) : showNoPrText ? (
            <span className="text-xs text-low whitespace-nowrap">
              {t('kanban.noPrCreated')}
            </span>
          ) : null}
        </div>
      </div>
    </IssueWorkspaceCardContainer>
  );
}

export function IssueWorkspaceCreateCard({
  onClick,
  className,
  shouldAnimateCreateButton = false,
}: IssueWorkspaceCreateCardProps) {
  const { t } = useTranslation('common');

  return (
    <IssueWorkspaceCardContainer
      className={cn('border border-dashed border-border', className)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-half min-w-0">
          <span className="px-1.5 py-0.5 rounded text-xs font-medium shrink-0 bg-secondary text-low">
            {t('workspaces.draft')}
          </span>
        </div>
      </div>

      <div className="flex items-center justify-between gap-base">
        <span className="text-sm text-low truncate">
          {t('workspaces.newWorkspace')}
        </span>
        <button
          type="button"
          onClick={onClick}
          disabled={!onClick}
          className={cn(
            'shrink-0 rounded-sm px-base py-half text-cta h-cta flex items-center bg-brand-secondary text-on-brand hover:bg-brand-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            shouldAnimateCreateButton && 'create-issue-attention'
          )}
        >
          {t('buttons.create')}
        </button>
      </div>
    </IssueWorkspaceCardContainer>
  );
}

function getTimeAgo(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const diffWeeks = Math.floor(diffDays / 7);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return `${diffWeeks}w ago`;
}

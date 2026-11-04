import { workspaceSidebarSections } from '../lib/workspaceSidebarSections';
import type { DotActivityState } from './DotActivityIndicators';
import type { ReactNode } from 'react';
import { useCallback, useMemo, useRef, useState } from 'react';
import {
  PlusIcon,
  ArrowLeftIcon,
  ArchiveIcon,
  StackIcon,
  SpinnerIcon,
  MagnifyingGlassIcon,
  XIcon,
} from '@phosphor-icons/react';
import { useTranslation } from 'react-i18next';
import { usePhoneLayout } from '../lib/usePhoneLayout';
import { cn } from '../lib/cn';
import { InputField } from './InputField';
import { WorkspaceSummary } from './WorkspaceSummary';
import { ProjectDotNotices, type ProjectDotNotice } from './ProjectDotNotices';
import type { AppBarHostStatus } from './AppBar';
import {
  CollapsibleSectionHeader,
  type SectionAction,
} from './CollapsibleSectionHeader';

export type WorkspaceLayoutMode = 'flat' | 'accordion';

export interface WorkspacesSidebarWorkspace extends DotActivityState {
  id: string;
  readLater?: boolean;
  name: string;
  dotManaged?: boolean;
  filesChanged?: number;
  linesAdded?: number;
  linesRemoved?: number;
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
}

export interface WorkspacesSidebarPersistKeys {
  raisedHand: string;
  readLater?: string;
  notRunning: string;
  running: string;
}

const DEFAULT_PERSIST_KEYS: WorkspacesSidebarPersistKeys = {
  raisedHand: 'workspaces-sidebar-raised-hand',
  readLater: 'workspaces-sidebar-read-later',
  notRunning: 'workspaces-sidebar-not-running',
  running: 'workspaces-sidebar-running',
};

export interface WorkspacesSidebarProps {
  projectDotNotices?: ProjectDotNotice[];
  onToggleProjectReadLater?: (projectId: string) => void;
  onToggleWorkspaceReadLater?: (workspaceId: string) => void;
  readLaterIssues?: ReactNode;
  readLaterIssueCount?: number;
  onOpenProjectChat?: (projectId: string) => void;
  workspaces: WorkspacesSidebarWorkspace[];
  /** Complete filtered collection for phone activity counts before pagination. */
  activityWorkspaces?: WorkspacesSidebarWorkspace[];
  totalWorkspacesCount: number;
  archivedWorkspaces?: WorkspacesSidebarWorkspace[];
  isLoading?: boolean;
  selectedWorkspaceId: string | null;
  onSelectWorkspace: (id: string) => void;
  onAddWorkspace?: () => void;
  searchQuery: string;
  onSearchChange: (value: string) => void;
  /** Whether we're in create mode */
  isCreateMode?: boolean;
  /** Title extracted from draft message (only shown when isCreateMode and non-empty) */
  draftTitle?: string;
  /** Handler to navigate back to create mode */
  onSelectCreate?: () => void;
  /** Whether to show archived workspaces */
  showArchive?: boolean;
  /** Handler for toggling archive view */
  onShowArchiveChange?: (show: boolean) => void;
  /** Layout mode for active workspaces */
  layoutMode?: WorkspaceLayoutMode;
  /** Handler for toggling layout mode */
  onToggleLayoutMode?: () => void;
  /** Handler to load more workspaces on scroll */
  onLoadMore?: () => void;
  /** Whether there are more workspaces to load */
  hasMoreWorkspaces?: boolean;
  /** Controls rendered beside the search input */
  searchControls?: ReactNode;
  /** Direct project controls rendered above the workspace list. */
  projectFilter?: ReactNode;
  assignmentControls?: ReactNode;
  /** Callback for opening workspace actions */
  onOpenWorkspaceActions?: (workspaceId: string) => void;
  /** Persist keys for collapsible sections */
  persistKeys?: WorkspacesSidebarPersistKeys;
  activeRemoteHost?: {
    name: string;
    status: AppBarHostStatus;
  } | null;
  onOpenRemoteHostSettings?: () => void;
}

export interface WorkspacesSidebarReopenTagProps {
  active?: boolean;
  onHoverStart?: () => void;
  onHoverEnd?: () => void;
  ariaLabel?: string;
  className?: string;
}

export function WorkspacesSidebarReopenTag({
  active = false,
  onHoverStart,
  onHoverEnd,
  ariaLabel,
  className,
}: WorkspacesSidebarReopenTagProps) {
  return (
    <button
      type="button"
      onMouseEnter={onHoverStart}
      onMouseLeave={onHoverEnd}
      aria-label={ariaLabel ?? 'Preview workspaces sidebar'}
      title={ariaLabel ?? 'Preview workspaces sidebar'}
      className={cn(
        'group inline-flex h-24 w-4 items-center justify-center rounded-md border border-border bg-secondary/95 shadow-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2 cursor-e-resize',
        active ? 'bg-panel text-normal' : 'text-low hover:text-normal',
        className
      )}
    >
      <span className="grid grid-cols-2 gap-[2px]">
        <span className="size-dot rounded-full bg-low/70 group-hover:bg-low" />
        <span className="size-dot rounded-full bg-low/70 group-hover:bg-low" />
        <span className="size-dot rounded-full bg-low/70 group-hover:bg-low" />
        <span className="size-dot rounded-full bg-low/70 group-hover:bg-low" />
        <span className="size-dot rounded-full bg-low/70 group-hover:bg-low" />
        <span className="size-dot rounded-full bg-low/70 group-hover:bg-low" />
      </span>
    </button>
  );
}

function WorkspaceList({
  workspaces,
  selectedWorkspaceId,
  onSelectWorkspace,
  onOpenWorkspaceActions,
  onToggleReadLater,
}: {
  workspaces: WorkspacesSidebarWorkspace[];
  selectedWorkspaceId: string | null;
  onSelectWorkspace: (id: string) => void;
  onOpenWorkspaceActions: (workspaceId: string) => void;
  onToggleReadLater?: (workspaceId: string) => void;
}) {
  return (
    <>
      {workspaces.map((workspace) => (
        <WorkspaceSummary
          key={workspace.id}
          readLater={workspace.readLater}
          onToggleReadLater={
            onToggleReadLater
              ? () => onToggleReadLater(workspace.id)
              : undefined
          }
          name={workspace.name}
          workspaceId={workspace.id}
          filesChanged={workspace.filesChanged}
          linesAdded={workspace.linesAdded}
          linesRemoved={workspace.linesRemoved}
          isActive={selectedWorkspaceId === workspace.id}
          isRunning={workspace.isRunning}
          isPinned={workspace.isPinned}
          hasPendingApproval={workspace.hasPendingApproval}
          hasRunningDevServer={workspace.hasRunningDevServer}
          hasUnseenActivity={workspace.hasUnseenActivity}
          dotManaged={workspace.dotManaged}
          dotUnreadCount={workspace.dotUnreadCount}
          dotNeedsAttentionCount={workspace.dotNeedsAttentionCount}
          activeSubagentCount={workspace.activeSubagentCount}
          unresolvedSubagentCount={workspace.unresolvedSubagentCount}
          latestProcessCompletedAt={workspace.latestProcessCompletedAt}
          latestProcessStatus={workspace.latestProcessStatus}
          prStatus={workspace.prStatus}
          onOpenWorkspaceActions={onOpenWorkspaceActions}
          onClick={() => onSelectWorkspace(workspace.id)}
        />
      ))}
    </>
  );
}

export function WorkspacesSidebar({
  projectDotNotices = [],
  onToggleProjectReadLater,
  onToggleWorkspaceReadLater,
  readLaterIssues,
  readLaterIssueCount = 0,
  onOpenProjectChat,
  workspaces,
  activityWorkspaces,
  totalWorkspacesCount,
  archivedWorkspaces = [],
  isLoading = false,
  selectedWorkspaceId,
  onSelectWorkspace,
  onAddWorkspace,
  searchQuery,
  onSearchChange,
  isCreateMode = false,
  draftTitle,
  onSelectCreate,
  showArchive = false,
  onShowArchiveChange,
  layoutMode = 'flat',
  onToggleLayoutMode,
  onLoadMore,
  hasMoreWorkspaces = false,
  searchControls,
  projectFilter,
  assignmentControls,
  onOpenWorkspaceActions,
  persistKeys = DEFAULT_PERSIST_KEYS,
  activeRemoteHost = null,
  onOpenRemoteHostSettings,
}: WorkspacesSidebarProps) {
  const { t } = useTranslation(['tasks', 'common']);
  const phone = usePhoneLayout();
  const [phoneCategory, setPhoneCategory] = useState('all');
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const projectNotices = onOpenProjectChat
    ? projectDotNotices.filter((item) => item.unreadCount > 0)
    : [];
  const attentionProjectNotices = projectNotices.filter(
    (notice) => !notice.readLater
  );
  const laterProjectNotices = projectNotices.filter(
    (notice) => notice.readLater
  );
  const projectRows = (
    <ProjectDotNotices
      notices={attentionProjectNotices}
      onOpen={onOpenProjectChat}
      onToggleReadLater={onToggleProjectReadLater}
    />
  );
  const laterProjectRows = (
    <ProjectDotNotices
      notices={laterProjectNotices}
      onOpen={onOpenProjectChat}
      onToggleReadLater={onToggleProjectReadLater}
    />
  );
  const handleOpenWorkspaceActions = useCallback(
    (workspaceId: string) => {
      onOpenWorkspaceActions?.(workspaceId);
    },
    [onOpenWorkspaceActions]
  );

  // Handle scroll to load more
  const handleScroll = () => {
    if (!hasMoreWorkspaces || !onLoadMore) return;

    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    // Load more when scrolled within 100px of the bottom
    if (scrollHeight - scrollTop - clientHeight < 100) {
      onLoadMore();
    }
  };

  const {
    raisedHandWorkspaces,
    readLaterWorkspaces,
    idleWorkspaces,
    runningWorkspaces,
  } = useMemo(
    () => workspaceSidebarSections(activityWorkspaces ?? workspaces),
    [workspaces, activityWorkspaces]
  );
  const renderWorkspaces = (rows: WorkspacesSidebarWorkspace[]) => (
    <WorkspaceList
      workspaces={rows}
      selectedWorkspaceId={selectedWorkspaceId}
      onSelectWorkspace={onSelectWorkspace}
      onOpenWorkspaceActions={handleOpenWorkspaceActions}
      onToggleReadLater={onToggleWorkspaceReadLater}
    />
  );
  const laterCount =
    readLaterWorkspaces.length +
    laterProjectNotices.length +
    readLaterIssueCount;
  const sections = [
    {
      id: 'attention',
      title: t('common:workspaces.attention'),
      rows: raisedHandWorkspaces,
      extra: projectRows,
      count: raisedHandWorkspaces.length + attentionProjectNotices.length,
      persistKey: persistKeys.raisedHand,
    },
    {
      id: 'later',
      title: t('common:workspaces.readLater'),
      rows: readLaterWorkspaces,
      extra: (
        <>
          {laterProjectRows}
          {readLaterIssues}
        </>
      ),
      count: laterCount,
      persistKey: persistKeys.readLater,
    },
    {
      id: 'running',
      title: t('common:workspaces.running'),
      rows: runningWorkspaces,
      count: runningWorkspaces.length,
      persistKey: persistKeys.running,
    },
    {
      id: 'ready',
      title: t('common:workspaces.completed'),
      rows: idleWorkspaces,
      count: idleWorkspaces.length,
      persistKey: persistKeys.notRunning,
    },
  ];
  const renderSections = (category = 'all') =>
    sections
      .filter((section) => category === 'all' || category === section.id)
      .map((section) => (
        <CollapsibleSectionHeader
          key={section.id}
          className="h-auto shrink-0"
          title={section.title}
          persistKey={section.persistKey}
          defaultExpanded={section.id !== 'later' || category !== 'all'}
          collapsible={
            section.id === 'later'
              ? category === 'all'
              : !phone && layoutMode === 'accordion'
          }
          headerExtra={
            <span className="text-xs text-low">{section.count}</span>
          }
        >
          <div
            className="flex flex-col gap-half py-half"
            data-workspace-section={section.id}
          >
            {section.extra}
            {section.id === 'attention' && draftTitle && (
              <WorkspaceSummary
                name={draftTitle}
                isActive={isCreateMode}
                isDraft
                onClick={onSelectCreate}
              />
            )}
            {renderWorkspaces(
              section.id === 'ready'
                ? section.rows.slice(0, workspaces.length)
                : section.rows
            )}
            {section.count === 0 && (
              <span className="text-sm text-low opacity-60 px-base">
                {section.id === 'later'
                  ? t('common:workspaces.noReadLater')
                  : t('common:workspaces.noWorkspaces')}
              </span>
            )}
          </div>
        </CollapsibleSectionHeader>
      ));

  const headerActions: SectionAction[] = [
    {
      icon: StackIcon,
      label: 'Switch workspace grouping',
      onClick: () => onToggleLayoutMode?.(),
      isActive: layoutMode === 'accordion',
    },
    {
      icon: PlusIcon,
      label: t('common:workspaces.newWorkspace'),
      onClick: () => onAddWorkspace?.(),
    },
  ];

  if (phone) {
    return (
      <div className="phone-workspaces">
        <div className="phone-page-heading">
          <div>
            <h1>{showArchive ? 'Archive' : t('common:workspaces.title')}</h1>
            <p>{totalWorkspacesCount} active workspaces</p>
          </div>
          <button
            type="button"
            className="phone-new-workspace"
            aria-label={t('common:workspaces.newWorkspace')}
            onClick={onAddWorkspace}
          >
            <PlusIcon size={20} /> New
          </button>
        </div>
        <div className="phone-workspace-search">
          <InputField
            className="phone-search-field"
            variant="search"
            leadingIcon={MagnifyingGlassIcon}
            ariaLabel="Search workspaces"
            value={searchQuery}
            onChange={onSearchChange}
            actionIcon={searchQuery ? XIcon : undefined}
            actionLabel="Clear search"
            onAction={() => onSearchChange('')}
            placeholder={t('common:workspaces.searchPlaceholder')}
          />
        </div>
        {(projectFilter || searchControls) && (
          <div className="phone-workspace-filters">
            {projectFilter}
            {searchControls}
          </div>
        )}
        {activeRemoteHost && (
          <button
            type="button"
            className="phone-host"
            onClick={onOpenRemoteHostSettings}
          >
            {activeRemoteHost.name} · {activeRemoteHost.status}
          </button>
        )}
        {assignmentControls && (
          <div className="px-base pb-half">{assignmentControls}</div>
        )}
        {!showArchive && (
          <div
            className="phone-filter-chips phone-workspace-tabs"
            aria-label="Workspace activity"
          >
            {[
              ['all', 'All', (activityWorkspaces ?? workspaces).length],
              [
                'attention',
                'Attention',
                raisedHandWorkspaces.length + attentionProjectNotices.length,
              ],
              ['later', t('common:workspaces.readLater'), laterCount],
              ['running', 'Running', runningWorkspaces.length],
              [
                'ready',
                t('common:workspaces.completed'),
                idleWorkspaces.length,
              ],
            ].map(([id, label, count]) => (
              <button
                key={id}
                type="button"
                aria-pressed={phoneCategory === id}
                onClick={() => setPhoneCategory(String(id))}
              >
                {label}
                <span>{count}</span>
              </button>
            ))}
          </div>
        )}
        <div
          ref={scrollContainerRef}
          onScroll={handleScroll}
          className="phone-workspace-scroll"
        >
          {isLoading ? (
            <SpinnerIcon className="animate-spin m-4" size={24} />
          ) : (
            <>
              {showArchive
                ? renderWorkspaces(archivedWorkspaces)
                : renderSections(phoneCategory)}
            </>
          )}
        </div>
        {onShowArchiveChange && (
          <button
            type="button"
            className="phone-archive"
            onClick={() => onShowArchiveChange(!showArchive)}
          >
            {showArchive ? (
              <ArrowLeftIcon size={20} />
            ) : (
              <ArchiveIcon size={20} />
            )}
            {showArchive ? 'Back to workspaces' : 'Archived workspaces'}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="w-full h-full bg-secondary flex flex-col">
      {/* Header + Search */}
      <div className="flex flex-col gap-base">
        <CollapsibleSectionHeader
          title={t('common:workspaces.title')}
          collapsible={false}
          actions={headerActions}
          className="border-b"
        />
        {assignmentControls && (
          <div className="px-base">{assignmentControls}</div>
        )}
        {!isLoading && (
          <div className="px-base flex items-stretch gap-half">
            <div className="flex-1 min-w-0">
              <InputField
                variant="search"
                ariaLabel="Search workspaces"
                value={searchQuery}
                onChange={onSearchChange}
                placeholder={t('common:workspaces.searchPlaceholder')}
              />
            </div>
            {searchControls}
          </div>
        )}

        {projectFilter && (
          <div className="px-base min-w-0">{projectFilter}</div>
        )}

        {activeRemoteHost && (
          <div className="px-base">
            <div className="rounded-sm border border-border bg-panel/60 px-base py-half flex items-center justify-between gap-base">
              <div className="min-w-0">
                <p className="text-xs text-low uppercase tracking-wide">
                  {t('common:workspaces.remoteHostLabel', {
                    defaultValue: 'Remote host',
                  })}
                </p>
                <p className="text-sm text-high truncate">
                  {activeRemoteHost.name}
                </p>
              </div>
              <div className="flex items-center gap-half shrink-0">
                <span
                  className={cn(
                    'inline-flex h-2.5 w-2.5 rounded-full',
                    activeRemoteHost.status === 'online'
                      ? 'bg-success'
                      : activeRemoteHost.status === 'offline'
                        ? 'bg-low'
                        : 'bg-warning'
                  )}
                  aria-hidden="true"
                />
                {onOpenRemoteHostSettings && (
                  <button
                    type="button"
                    onClick={onOpenRemoteHostSettings}
                    className="text-xs text-brand hover:underline"
                  >
                    {t('common:workspaces.remoteHostManage', {
                      defaultValue: 'Manage',
                    })}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Scrollable workspace list */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto py-base"
      >
        {isLoading ? (
          <div className="flex h-full min-h-[220px] items-center justify-center px-base">
            <div className="flex items-center justify-center text-low">
              <SpinnerIcon className="size-6 animate-spin" weight="bold" />
            </div>
          </div>
        ) : showArchive ? (
          /* Archived workspaces view */
          <div className="flex flex-col gap-base">
            <span className="text-sm font-medium text-low px-base">
              {t('common:workspaces.archived')}
            </span>
            {archivedWorkspaces.length === 0 ? (
              <span className="text-sm text-low opacity-60 px-base">
                {t('common:workspaces.noArchived')}
              </span>
            ) : (
              archivedWorkspaces.map((workspace) => (
                <WorkspaceSummary
                  summary
                  key={workspace.id}
                  name={workspace.name}
                  workspaceId={workspace.id}
                  filesChanged={workspace.filesChanged}
                  linesAdded={workspace.linesAdded}
                  linesRemoved={workspace.linesRemoved}
                  isActive={selectedWorkspaceId === workspace.id}
                  isRunning={workspace.isRunning}
                  isPinned={workspace.isPinned}
                  hasPendingApproval={workspace.hasPendingApproval}
                  hasRunningDevServer={workspace.hasRunningDevServer}
                  hasUnseenActivity={workspace.hasUnseenActivity}
                  dotManaged={workspace.dotManaged}
                  dotUnreadCount={workspace.dotUnreadCount}
                  dotNeedsAttentionCount={workspace.dotNeedsAttentionCount}
                  latestProcessCompletedAt={workspace.latestProcessCompletedAt}
                  latestProcessStatus={workspace.latestProcessStatus}
                  prStatus={workspace.prStatus}
                  onOpenWorkspaceActions={handleOpenWorkspaceActions}
                  onClick={() => onSelectWorkspace(workspace.id)}
                />
              ))
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-base">{renderSections()}</div>
        )}
      </div>

      {/* Fixed footer toggle - only show if there are archived workspaces */}
      <div className="border-t border-primary p-base">
        <button
          onClick={() => onShowArchiveChange?.(!showArchive)}
          className="w-full flex items-center gap-base text-sm text-low hover:text-normal transition-colors duration-100"
        >
          {showArchive ? (
            <>
              <ArrowLeftIcon className="size-icon-xs" />
              <span>{t('common:workspaces.backToActive')}</span>
            </>
          ) : (
            <>
              <ArchiveIcon className="size-icon-xs" />
              <span>{t('common:workspaces.viewArchive')}</span>
              <span className="ml-auto text-xs bg-tertiary px-1.5 py-0.5 rounded">
                {archivedWorkspaces.length}
              </span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}

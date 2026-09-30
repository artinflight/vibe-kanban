import {
  DragDropContext,
  Draggable,
  Droppable,
  type DropResult,
} from '@hello-pangea/dnd';
import { useState, type ReactNode } from 'react';
import {
  LayoutIcon,
  DownloadSimpleIcon,
  LinkIcon,
  PlusIcon,
  ArchiveIcon,
  KanbanIcon,
  SpinnerIcon,
  StarIcon,
  CaretRightIcon,
  CaretLeftIcon,
  PencilSimpleIcon,
  type Icon,
} from '@phosphor-icons/react';
import { cn } from '../lib/cn';
import { AppBarSocialLink } from './AppBarSocialLink';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverClose,
} from './Popover';
import { Tooltip } from './Tooltip';
import { useTranslation } from 'react-i18next';
import { InlineColorPicker } from './ColorPicker';
import { Input } from './Input';
import { Button } from './Button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './KeyboardDialog';

export const PASTEL_PROJECT_COLORS = [
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

function formatStarCount(count: number): string {
  if (count < 1000) return String(count);
  const k = count / 1000;
  return k >= 10 ? `${Math.floor(k)}k` : `${k.toFixed(1)}k`;
}

function getProjectInitials(name: string): string {
  const trimmed = name.trim();
  if (!trimmed) return '??';

  const words = trimmed.split(/[\s_-]+/).filter(Boolean);
  if (words.length >= 2) {
    return (
      words[0].charAt(0) + words[words.length - 1].charAt(0)
    ).toUpperCase();
  }
  return trimmed.slice(0, 2).toUpperCase();
}

function getProjectAbbreviation(project: AppBarProject): string {
  const abbreviation = project.abbreviation?.trim();
  if (abbreviation) return abbreviation.slice(0, 3).toUpperCase();
  return getProjectInitials(project.name);
}

function getProjectButtonStyle(project: AppBarProject, isActive: boolean) {
  return {
    backgroundColor: `hsl(${project.color} / ${isActive ? 1 : 0.72})`,
    color: 'hsl(222 35% 18%)',
    boxShadow: isActive ? `0 0 0 2px hsl(${project.color} / 0.35)` : undefined,
  };
}

interface AppBarProps {
  projects: AppBarProject[];
  hosts?: AppBarHost[];
  onPairHostClick?: () => void;
  activeHostId?: string | null;
  onCreateProject: () => void;
  onOpenArchivedProjects?: () => void;
  hasArchivedProjects?: boolean;
  onExportClick?: () => void;
  onWorkspacesClick: () => void;
  onHostClick?: (hostId: string, status: AppBarHostStatus) => void;
  showWorkspacesButton?: boolean;
  showRemoteSection?: boolean;
  showExportButton?: boolean;
  showProfileButton?: boolean;
  showSocialLinks?: boolean;
  onProjectClick: (projectId: string) => void;
  onProjectsDragEnd: (result: DropResult) => void;
  onProjectUpdate?: (
    projectId: string,
    updates: AppBarProjectUpdate
  ) => Promise<void> | void;
  isSavingProjectOrder?: boolean;
  isWorkspacesActive: boolean;
  isExportActive?: boolean;
  activeProjectId: string | null;
  isSignedIn?: boolean;
  isLoadingProjects?: boolean;
  onSignIn?: () => void;
  onHoverStart?: () => void;
  onHoverEnd?: () => void;
  notificationBell?: ReactNode;
  userPopover?: ReactNode;
  starCount?: number | null;
  onlineCount?: number | null;
  appVersion?: string | null;
  updateVersion?: string | null;
  onUpdateClick?: () => void;
  githubIconPath: string;
  discordIconPath: string;
}

export interface AppBarProject {
  id: string;
  name: string;
  color: string;
  abbreviation?: string;
  archived?: boolean;
  hasNeedsReview?: boolean;
}

export interface AppBarProjectUpdate {
  name: string;
  abbreviation: string;
  color: string;
}

export type AppBarHostStatus = 'online' | 'offline' | 'unpaired';

export interface AppBarHost {
  id: string;
  name: string;
  status: AppBarHostStatus;
}

function getHostStatusLabel(status: AppBarHostStatus): string {
  if (status === 'online') return 'Online';
  if (status === 'offline') return 'Offline';
  return 'Unpaired';
}

function getHostStatusIndicatorClass(status: AppBarHostStatus): string {
  if (status === 'online') return 'bg-success';
  if (status === 'offline') return 'bg-low';
  return 'bg-white border-warning';
}

function AppBarSectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="w-10 text-center text-[9px] font-medium leading-none tracking-wide text-low">
      {children}
    </p>
  );
}

const appBarItemBaseClassName =
  'flex items-center justify-center w-10 h-10 rounded-lg text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand';

type AppBarSection = {
  key: 'local' | 'remote' | 'projects' | 'export';
  label: string;
  items: AppBarSectionItem[];
};

type AppBarSectionItem =
  | {
      key: string;
      kind: 'icon-button';
      label: string;
      icon: Icon;
      isActive?: boolean;
      onClick?: () => void;
      className?: string;
      wrapperClassName?: string;
    }
  | {
      key: string;
      kind: 'host-button';
      host: AppBarHost;
      isActive: boolean;
      onClick?: () => void;
      wrapperClassName?: string;
    }
  | {
      key: string;
      kind: 'kanban-cta';
      label: string;
      onSignIn?: () => void;
    }
  | {
      key: string;
      kind: 'loading';
    }
  | {
      key: string;
      kind: 'project-list';
      projects: AppBarProject[];
      activeProjectId: string | null;
      isSavingProjectOrder?: boolean;
      onProjectClick: (projectId: string) => void;
      onProjectsDragEnd: (result: DropResult) => void;
      onProjectUpdate?: (
        projectId: string,
        updates: AppBarProjectUpdate
      ) => Promise<void> | void;
      archived?: boolean;
    };

function getStandardAppBarButtonClassName({
  isActive = false,
  className,
}: {
  isActive?: boolean;
  className?: string;
}) {
  return cn(
    appBarItemBaseClassName,
    'cursor-pointer',
    isActive
      ? 'bg-brand/20 text-brand hover:bg-brand/20'
      : 'bg-primary text-normal hover:bg-brand/10',
    className
  );
}

function getHostButtonClassName({
  host,
  isActive,
}: {
  host: AppBarHost;
  isActive: boolean;
}) {
  const isOffline = host.status === 'offline';

  return cn(
    appBarItemBaseClassName,
    isOffline
      ? 'bg-primary text-low opacity-50 cursor-not-allowed'
      : isActive
        ? 'bg-brand/20 text-brand cursor-pointer hover:bg-brand/20'
        : host.status === 'unpaired'
          ? 'bg-primary text-warning cursor-pointer hover:bg-warning/10'
          : 'bg-primary text-normal cursor-pointer hover:bg-brand/10'
  );
}

export function AppBar({
  projects,
  hosts = [],
  onPairHostClick,
  activeHostId = null,
  onCreateProject,
  onOpenArchivedProjects,
  hasArchivedProjects = false,
  onExportClick,
  onWorkspacesClick,
  onHostClick,
  showWorkspacesButton = true,
  showRemoteSection = true,
  showExportButton = true,
  showProfileButton = true,
  showSocialLinks = true,
  onProjectClick,
  onProjectsDragEnd,
  onProjectUpdate,
  isSavingProjectOrder,
  isWorkspacesActive,
  isExportActive = false,
  activeProjectId,
  isSignedIn,
  isLoadingProjects,
  onSignIn,
  onHoverStart,
  onHoverEnd,
  notificationBell,
  userPopover,
  starCount,
  onlineCount,
  appVersion,
  updateVersion,
  onUpdateClick,
  githubIconPath,
  discordIconPath,
}: AppBarProps) {
  const { t } = useTranslation('common');
  const [isProjectFlyoutOpen, setIsProjectFlyoutOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<AppBarProject | null>(
    null
  );
  const [projectDraft, setProjectDraft] = useState<AppBarProjectUpdate>({
    name: '',
    abbreviation: '',
    color: PASTEL_PROJECT_COLORS[0],
  });
  const [projectEditError, setProjectEditError] = useState<string | null>(null);
  const [isSavingProjectEdit, setIsSavingProjectEdit] = useState(false);
  const sections: AppBarSection[] = [];

  const openProjectEditor = (project: AppBarProject) => {
    setEditingProject(project);
    setProjectDraft({
      name: project.name,
      abbreviation: getProjectAbbreviation(project),
      color: project.color || PASTEL_PROJECT_COLORS[0],
    });
    setProjectEditError(null);
  };

  const closeProjectEditor = () => {
    if (isSavingProjectEdit) return;
    setEditingProject(null);
    setProjectEditError(null);
  };

  const handleSaveProjectEdit = async () => {
    if (!editingProject || !onProjectUpdate) {
      closeProjectEditor();
      return;
    }

    const nextName = projectDraft.name.trim();
    const nextAbbreviation = projectDraft.abbreviation.trim().slice(0, 3);
    if (!nextName) {
      setProjectEditError('Project name is required.');
      return;
    }
    if (!nextAbbreviation) {
      setProjectEditError('Abbreviation is required.');
      return;
    }

    setIsSavingProjectEdit(true);
    setProjectEditError(null);
    try {
      await onProjectUpdate(editingProject.id, {
        name: nextName,
        abbreviation: nextAbbreviation,
        color: projectDraft.color,
      });
      setEditingProject(null);
    } catch (error) {
      setProjectEditError(
        error instanceof Error ? error.message : 'Failed to update project.'
      );
    } finally {
      setIsSavingProjectEdit(false);
    }
  };

  if (showWorkspacesButton) {
    sections.push({
      key: 'local',
      label: 'Local',
      items: [
        {
          key: 'local-workspaces',
          kind: 'icon-button',
          label: 'Local workspaces',
          icon: LayoutIcon,
          isActive: isWorkspacesActive,
          onClick: onWorkspacesClick,
        },
      ],
    });
  }

  if (showRemoteSection && (hosts.length > 0 || onPairHostClick)) {
    sections.push({
      key: 'remote',
      label: 'Remote',
      items: [
        ...hosts.map((host) => ({
          key: `host-${host.id}`,
          kind: 'host-button' as const,
          host,
          isActive: host.id === activeHostId,
          onClick: () => {
            if (host.status === 'offline') {
              return;
            }

            onHostClick?.(host.id, host.status);
          },
        })),
        ...(onPairHostClick
          ? [
              {
                key: 'pair-remote-device',
                kind: 'icon-button' as const,
                label: 'Pair a remote device',
                icon: LinkIcon,
                onClick: onPairHostClick,
                className:
                  'bg-primary text-muted hover:text-normal hover:bg-tertiary',
              },
            ]
          : []),
      ],
    });
  }

  const projectSectionItems: AppBarSectionItem[] = [];

  if (!isSignedIn) {
    projectSectionItems.push({
      key: 'kanban-cta',
      kind: 'kanban-cta',
      label: t('appBar.kanban.tooltip'),
      onSignIn,
    });
  }

  if (isLoadingProjects) {
    projectSectionItems.push({ key: 'projects-loading', kind: 'loading' });
  }

  if (projects.length > 0) {
    projectSectionItems.push({
      key: 'project-list',
      kind: 'project-list',
      projects,
      activeProjectId,
      isSavingProjectOrder,
      onProjectClick,
      onProjectsDragEnd,
      onProjectUpdate,
    });
  }

  if (isSignedIn) {
    projectSectionItems.push({
      key: 'create-project',
      kind: 'icon-button',
      label: 'Create project',
      icon: PlusIcon,
      onClick: onCreateProject,
      className: 'bg-primary text-muted hover:text-normal hover:bg-tertiary',
      wrapperClassName: 'pt-base',
    });

    if (hasArchivedProjects && onOpenArchivedProjects) {
      projectSectionItems.push({
        key: 'open-archived-projects',
        kind: 'icon-button',
        label: 'Archived projects',
        icon: ArchiveIcon,
        onClick: onOpenArchivedProjects,
        className: 'bg-primary text-muted hover:text-normal hover:bg-tertiary',
      });
    }
  }

  if (projectSectionItems.length > 0) {
    sections.push({
      key: 'projects',
      label: 'Projects',
      items: projectSectionItems,
    });
  }

  if (showExportButton && isSignedIn && onExportClick) {
    sections.push({
      key: 'export',
      label: 'Export',
      items: [
        {
          key: 'export-data',
          kind: 'icon-button',
          label: 'Export data',
          icon: DownloadSimpleIcon,
          isActive: isExportActive,
          onClick: onExportClick,
        },
      ],
    });
  }

  function renderSectionItem(item: AppBarSectionItem): ReactNode {
    switch (item.kind) {
      case 'icon-button':
        return (
          <Tooltip content={item.label} side="right">
            <button
              type="button"
              onClick={item.onClick}
              className={getStandardAppBarButtonClassName({
                isActive: item.isActive,
                className: item.className,
              })}
              aria-label={item.label}
            >
              <item.icon className="size-icon-base" weight="bold" />
            </button>
          </Tooltip>
        );
      case 'host-button': {
        const isOffline = item.host.status === 'offline';

        return (
          <Tooltip
            content={`${item.host.name} · ${getHostStatusLabel(item.host.status)}`}
            side="right"
          >
            <div className="relative">
              <span
                className={cn(
                  'absolute -top-1 -right-1 z-10',
                  'w-3.5 h-3.5 rounded-full border border-secondary',
                  getHostStatusIndicatorClass(item.host.status)
                )}
                aria-hidden="true"
              />
              <button
                type="button"
                disabled={isOffline}
                onClick={item.onClick}
                className={getHostButtonClassName({
                  host: item.host,
                  isActive: item.isActive,
                })}
                aria-label={`${item.host.name} (${getHostStatusLabel(item.host.status)})`}
              >
                {getProjectInitials(item.host.name)}
              </button>
            </div>
          </Tooltip>
        );
      }
      case 'kanban-cta':
        return (
          <Popover>
            <Tooltip content={item.label} side="right">
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className={getStandardAppBarButtonClassName({})}
                  aria-label={item.label}
                >
                  <KanbanIcon className="size-icon-base" weight="bold" />
                </button>
              </PopoverTrigger>
            </Tooltip>
            <PopoverContent side="right" sideOffset={8}>
              <p className="text-sm font-medium text-high">
                {t('appBar.kanban.title')}
              </p>
              <p className="text-xs text-low mt-1">
                {t('appBar.kanban.description')}
              </p>
              <div className="mt-base">
                <PopoverClose asChild>
                  <button
                    type="button"
                    onClick={item.onSignIn}
                    className={cn(
                      'px-base py-1 rounded-sm text-xs',
                      'bg-brand text-on-brand hover:bg-brand-hover cursor-pointer'
                    )}
                  >
                    {t('signIn')}
                  </button>
                </PopoverClose>
              </div>
            </PopoverContent>
          </Popover>
        );
      case 'loading':
        return (
          <div className="flex items-center justify-center w-10 h-10">
            <SpinnerIcon className="size-5 animate-spin text-muted" />
          </div>
        );
      case 'project-list':
        return (
          <DragDropContext onDragEnd={item.onProjectsDragEnd}>
            <Droppable
              droppableId={
                item.archived ? 'app-bar-archived-projects' : 'app-bar-projects'
              }
              direction="vertical"
              isDropDisabled={item.isSavingProjectOrder || item.archived}
            >
              {(dropProvided) => (
                <div
                  ref={dropProvided.innerRef}
                  {...dropProvided.droppableProps}
                  className="flex h-full min-h-0 flex-col items-center gap-half overflow-y-auto overflow-x-hidden py-half"
                >
                  {item.projects.map((project, index) => (
                    <Draggable
                      key={project.id}
                      draggableId={project.id}
                      index={index}
                      disableInteractiveElementBlocking
                      isDragDisabled={
                        item.isSavingProjectOrder || item.archived
                      }
                    >
                      {(dragProvided, snapshot) => (
                        <div
                          ref={dragProvided.innerRef}
                          {...dragProvided.draggableProps}
                          {...dragProvided.dragHandleProps}
                          className="flex h-10 w-10 shrink-0 items-center justify-center"
                          style={dragProvided.draggableProps.style}
                        >
                          <Tooltip content={project.name} side="right">
                            <div className="relative h-10 w-10">
                              {project.hasNeedsReview && (
                                <span
                                  className="absolute -right-1 -top-1 z-10 h-3 w-3 rounded-full border border-secondary bg-brand"
                                  aria-hidden="true"
                                />
                              )}
                              <button
                                type="button"
                                onClick={() => item.onProjectClick(project.id)}
                                className={cn(
                                  appBarItemBaseClassName,
                                  '!h-full !w-full',
                                  item.archived
                                    ? 'cursor-pointer'
                                    : 'cursor-grab',
                                  snapshot.isDragging && 'shadow-lg',
                                  item.archived
                                    ? 'opacity-70 hover:opacity-100'
                                    : 'hover:opacity-85'
                                )}
                                style={getProjectButtonStyle(
                                  project,
                                  item.activeProjectId === project.id
                                )}
                                aria-label={
                                  project.hasNeedsReview
                                    ? `${project.name} (needs review)`
                                    : project.name
                                }
                              >
                                {getProjectAbbreviation(project)}
                              </button>
                            </div>
                          </Tooltip>
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {dropProvided.placeholder}
                </div>
              )}
            </Droppable>
          </DragDropContext>
        );
    }
  }

  return (
    <div
      onMouseEnter={onHoverStart}
      onMouseLeave={onHoverEnd}
      className="relative z-30 h-full shrink-0"
    >
      <div
        className={cn(
          'flex h-full min-h-0 w-16 flex-col items-center overflow-hidden p-base gap-base',
          'bg-secondary border-r border-border'
        )}
      >
        {sections.map((section) => (
          <div
            key={section.key}
            className={cn(
              'flex flex-col items-center gap-1',
              section.key === 'projects' ? 'min-h-0 flex-1' : 'shrink-0'
            )}
          >
            <AppBarSectionLabel>{section.label}</AppBarSectionLabel>
            {section.items.map((item) => (
              <div
                key={item.key}
                className={cn(
                  item.kind === 'project-list' && 'min-h-0 flex-1',
                  'wrapperClassName' in item ? item.wrapperClassName : undefined
                )}
              >
                {renderSectionItem(item)}
              </div>
            ))}
          </div>
        ))}

        {/* Bottom section: Notifications + User popover + GitHub + Discord */}
        <div className="mt-auto pt-base flex flex-col items-center gap-4">
          {notificationBell}
          {showProfileButton ? userPopover : null}
          {showSocialLinks ? (
            <>
              <AppBarSocialLink
                href="https://github.com/BloopAI/vibe-kanban"
                label="Star on GitHub"
                iconPath={githubIconPath}
                badge={
                  starCount != null && (
                    <>
                      <StarIcon size={10} weight="fill" />
                      {formatStarCount(starCount)}
                    </>
                  )
                }
              />
              <AppBarSocialLink
                href="https://discord.gg/AC4nwVtJM3"
                label="Join our Discord"
                iconPath={discordIconPath}
                badge={
                  onlineCount != null &&
                  (onlineCount > 999 ? '999+' : onlineCount)
                }
              />
            </>
          ) : null}
          {updateVersion ? (
            <Tooltip content={`Update to v${updateVersion}`} side="right">
              <button
                type="button"
                onClick={onUpdateClick}
                className={cn(
                  'flex items-center justify-center py-1 rounded-md w-10',
                  'text-[9px] font-ibm-plex-mono font-medium leading-none',
                  'bg-brand text-on-brand hover:bg-brand-hover',
                  'transition-colors cursor-pointer'
                )}
              >
                Update
              </button>
            </Tooltip>
          ) : (
            appVersion && (
              <p
                className="text-[9px] font-ibm-plex-mono text-low leading-none truncate max-w-10 text-center"
                title={`v${appVersion}`}
              >
                v{appVersion}
              </p>
            )
          )}
        </div>
      </div>

      {projects.length > 0 && (
        <Tooltip
          content={
            isProjectFlyoutOpen ? 'Hide project names' : 'Show project names'
          }
          side="right"
        >
          <button
            type="button"
            onClick={() => setIsProjectFlyoutOpen((open) => !open)}
            className={cn(
              'absolute left-full top-20 z-40 flex h-9 w-5 items-center justify-center',
              'rounded-r-md border border-l-0 border-border bg-secondary text-low',
              'shadow-sm transition-colors hover:text-normal'
            )}
            aria-label={
              isProjectFlyoutOpen ? 'Hide project names' : 'Show project names'
            }
            aria-expanded={isProjectFlyoutOpen}
          >
            {isProjectFlyoutOpen ? (
              <CaretLeftIcon className="h-3.5 w-3.5" weight="bold" />
            ) : (
              <CaretRightIcon className="h-3.5 w-3.5" weight="bold" />
            )}
          </button>
        </Tooltip>
      )}

      <div
        className={cn(
          'absolute left-full top-0 z-30 h-full w-72 border-r border-border bg-secondary shadow-lg',
          'transition-[opacity,transform] duration-150 ease-out',
          isProjectFlyoutOpen
            ? 'translate-x-0 opacity-100 pointer-events-auto'
            : '-translate-x-2 opacity-0 pointer-events-none'
        )}
        aria-hidden={!isProjectFlyoutOpen}
      >
        <div className="flex h-full min-h-0 flex-col">
          <div className="flex items-center justify-between border-b border-border px-base py-base">
            <p className="text-sm font-medium text-high">Projects</p>
            <button
              type="button"
              onClick={() => setIsProjectFlyoutOpen(false)}
              className="rounded-sm p-half text-low hover:bg-primary hover:text-normal"
              aria-label="Hide project names"
            >
              <CaretLeftIcon className="h-4 w-4" weight="bold" />
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-base">
            <div className="space-y-half">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className={cn(
                    'flex min-h-10 items-center gap-half rounded-sm px-half py-half',
                    activeProjectId === project.id
                      ? 'bg-primary'
                      : 'hover:bg-primary/70'
                  )}
                >
                  <button
                    type="button"
                    onClick={() => onProjectClick(project.id)}
                    className="flex min-w-0 flex-1 items-center gap-half text-left"
                  >
                    <span
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-xs font-semibold"
                      style={getProjectButtonStyle(
                        project,
                        activeProjectId === project.id
                      )}
                    >
                      {getProjectAbbreviation(project)}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-sm text-normal">
                      {project.name}
                    </span>
                  </button>
                  {project.hasNeedsReview && (
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full bg-brand"
                      title="Needs review"
                    />
                  )}
                  {onProjectUpdate && !project.archived && (
                    <button
                      type="button"
                      onClick={() => openProjectEditor(project)}
                      className="shrink-0 rounded-sm p-half text-low hover:bg-secondary hover:text-normal"
                      aria-label={`Edit ${project.name}`}
                    >
                      <PencilSimpleIcon className="h-4 w-4" weight="bold" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Dialog open={!!editingProject} onOpenChange={closeProjectEditor}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Edit project</DialogTitle>
            <DialogDescription>
              Rename the project, set its sidebar abbreviation, and choose a
              pastel button color.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-base">
            <div className="space-y-half">
              <label
                htmlFor="app-bar-project-name"
                className="text-sm text-normal"
              >
                Name
              </label>
              <Input
                id="app-bar-project-name"
                value={projectDraft.name}
                disabled={isSavingProjectEdit}
                maxLength={100}
                onChange={(event) =>
                  setProjectDraft((draft) => ({
                    ...draft,
                    name: event.target.value,
                  }))
                }
                onCommandEnter={() => void handleSaveProjectEdit()}
              />
            </div>

            <div className="space-y-half">
              <label
                htmlFor="app-bar-project-abbreviation"
                className="text-sm text-normal"
              >
                Abbreviation
              </label>
              <Input
                id="app-bar-project-abbreviation"
                value={projectDraft.abbreviation}
                disabled={isSavingProjectEdit}
                maxLength={3}
                onChange={(event) =>
                  setProjectDraft((draft) => ({
                    ...draft,
                    abbreviation: event.target.value.toUpperCase(),
                  }))
                }
                onCommandEnter={() => void handleSaveProjectEdit()}
              />
            </div>

            <div className="space-y-half">
              <p className="text-sm text-normal">Color</p>
              <InlineColorPicker
                value={projectDraft.color}
                onChange={(color) =>
                  setProjectDraft((draft) => ({ ...draft, color }))
                }
                colors={PASTEL_PROJECT_COLORS}
                disabled={isSavingProjectEdit}
              />
            </div>

            {projectEditError && (
              <p className="text-sm text-error">{projectEditError}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={closeProjectEditor}
              disabled={isSavingProjectEdit}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={() => void handleSaveProjectEdit()}
              disabled={isSavingProjectEdit}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

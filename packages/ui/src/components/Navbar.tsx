import { type ButtonHTMLAttributes, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { MobileDrawer } from './MobileDrawer';
import type { Icon } from '@phosphor-icons/react';
import {
  Layout as LayoutIcon,
  ChatsTeardrop as ChatsTeardropIcon,
  GitDiff as GitDiffIcon,
  Terminal as TerminalIcon,
  Desktop as DesktopIcon,
  GitFork as GitForkIcon,
  List as ListIcon,
  Gear as GearIcon,
  Kanban as KanbanIcon,
  CaretLeft as CaretLeftIcon,
  DotsThree as DotsThreeIcon,
  SidebarSimple as SidebarSimpleIcon,
} from '@phosphor-icons/react';
import { cn } from '../lib/cn';
import { Tooltip } from './Tooltip';
import {
  SyncErrorIndicator,
  type SyncErrorIndicatorError,
} from './SyncErrorIndicator';

/**
 * Action item rendered in the navbar.
 */
export interface NavbarActionItem {
  type?: 'action';
  id: string;
  icon: Icon;
  isActive?: boolean;
  tooltip?: string;
  shortcut?: string;
  disabled?: boolean;
  onClick?: () => void;
}

/**
 * Divider item rendered in the navbar.
 */
export interface NavbarDividerItem {
  type: 'divider';
}

export type NavbarSectionItem = NavbarActionItem | NavbarDividerItem;

function isDivider(item: NavbarSectionItem): item is NavbarDividerItem {
  return item.type === 'divider';
}

// NavbarIconButton - inlined from primitives
interface NavbarIconButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: Icon;
  isActive?: boolean;
  tooltip?: string;
  shortcut?: string;
}

function NavbarIconButton({
  icon: IconComponent,
  isActive = false,
  tooltip,
  shortcut,
  className,
  ...props
}: NavbarIconButtonProps) {
  const button = (
    <button
      type="button"
      className={cn(
        'flex items-center justify-center rounded-sm',
        'text-low hover:text-normal',
        isActive && 'text-normal',
        className
      )}
      {...props}
    >
      <IconComponent
        className="size-icon-base"
        weight={isActive ? 'fill' : 'regular'}
      />
    </button>
  );

  return tooltip ? (
    <Tooltip content={tooltip} shortcut={shortcut}>
      {button}
    </Tooltip>
  ) : (
    button
  );
}

export type MobileTabId =
  | 'workspaces'
  | 'chat'
  | 'changes'
  | 'logs'
  | 'preview'
  | 'git';

export const MOBILE_TABS: { id: MobileTabId; icon: Icon; label: string }[] = [
  { id: 'workspaces', icon: LayoutIcon, label: 'Workspaces' },
  { id: 'chat', icon: ChatsTeardropIcon, label: 'Chat' },
  { id: 'changes', icon: GitDiffIcon, label: 'Changes' },
  { id: 'logs', icon: TerminalIcon, label: 'Logs' },
  { id: 'preview', icon: DesktopIcon, label: 'Preview' },
  { id: 'git', icon: GitForkIcon, label: 'Git' },
];

export interface NavbarBreadcrumbItem {
  label: string;
  onClick?: () => void;
}

interface NavbarBreadcrumbsProps {
  breadcrumbs: NavbarBreadcrumbItem[];
  textClassName: string;
}

function NavbarBreadcrumbs({
  breadcrumbs,
  textClassName,
}: NavbarBreadcrumbsProps) {
  return (
    <div className={cn('flex items-center gap-1 min-w-0', textClassName)}>
      {breadcrumbs.map((crumb, index) => {
        const isLast = index === breadcrumbs.length - 1;
        return (
          <span key={index} className="flex items-center gap-1 min-w-0">
            {index > 0 && <span className="text-low shrink-0">/</span>}
            {crumb.onClick && !isLast ? (
              <button
                type="button"
                className="text-low hover:text-normal truncate cursor-pointer"
                onClick={crumb.onClick}
              >
                {crumb.label}
              </button>
            ) : (
              <span
                className={cn('truncate', isLast ? 'text-normal' : 'text-low')}
              >
                {crumb.label}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}

export interface NavbarProps {
  workspaceTitle?: string;
  breadcrumbs?: NavbarBreadcrumbItem[];
  // Items for left side of navbar
  leftItems?: NavbarSectionItem[];
  // Items for right side of navbar (with dividers inline)
  rightItems?: NavbarSectionItem[];
  // Optional additional content for left side (after leftItems)
  leftSlot?: ReactNode;
  // Sync errors shown in the right section
  syncErrors?: readonly SyncErrorIndicatorError[] | null;
  className?: string;
  // Mobile props
  mobileMode?: boolean;
  mobileMoreOpen?: boolean;
  onOpenMobileMore?: () => void;
  onCloseMobileMore?: () => void;
  onMobileMoreAction?: (action: () => void) => void;
  mobileNavigationSlot?: HTMLElement | null;
  mobileUserSlot?: ReactNode;
  isOnProjectPage?: boolean;
  onOpenCommandBar?: () => void;
  onOpenSettings?: () => void;
  onNavigateToBoard?: (() => void) | null;
  onNavigateBack?: () => void;
  onReload?: () => void;
  onOpenDrawer?: () => void;
  isOnProjectSubRoute?: boolean;
  mobileActiveTab?: MobileTabId;
  onMobileTabChange?: (tab: MobileTabId) => void;
  mobileTabs?: { id: MobileTabId; icon: Icon; label: string }[];
  showMobileTabs?: boolean;
  mobileShowBack?: boolean;
}

export function Navbar({
  workspaceTitle,
  breadcrumbs,
  leftItems = [],
  rightItems = [],
  leftSlot,
  syncErrors,
  className,
  mobileMode = false,
  mobileMoreOpen: moreOpen = false,
  onOpenMobileMore,
  onCloseMobileMore,
  onMobileMoreAction,
  mobileNavigationSlot,
  mobileUserSlot,
  isOnProjectPage = false,
  onOpenCommandBar,
  onOpenSettings,
  onNavigateToBoard,
  onNavigateBack,
  onReload,
  onOpenDrawer,
  isOnProjectSubRoute = false,
  mobileActiveTab = 'chat',
  onMobileTabChange,
  mobileTabs,
  showMobileTabs,
  mobileShowBack,
}: NavbarProps) {
  const runMoreAction =
    onMobileMoreAction ?? ((action: () => void) => action());
  const renderItem = (item: NavbarSectionItem, key: string) => {
    // Render divider
    if (isDivider(item)) {
      return <div key={key} className="h-4 w-px bg-border" />;
    }

    const isDisabled = !!item.disabled;

    return (
      <NavbarIconButton
        key={key}
        icon={item.icon}
        isActive={item.isActive}
        onClick={item.onClick}
        aria-label={item.tooltip}
        tooltip={item.tooltip}
        shortcut={item.shortcut}
        disabled={isDisabled}
        className={isDisabled ? 'opacity-40 cursor-not-allowed' : ''}
      />
    );
  };

  // The shell supplies a bottom slot so navigation participates in the flex
  // layout instead of covering the composer or scrolled task content.
  if (mobileMode) {
    const tabs = mobileTabs ?? MOBILE_TABS;
    const navigationSlot = mobileNavigationSlot;
    const primaryTabs = tabs.filter((tab) =>
      ['workspaces', 'chat', 'changes'].includes(tab.id)
    );
    const secondaryTabs = tabs.filter(
      (tab) => !['workspaces', 'chat', 'changes'].includes(tab.id)
    );
    const isSecondaryActive = secondaryTabs.some(
      (tab) => tab.id === mobileActiveTab
    );
    const navigation = (
      <nav className="mobile-bottom-navigation" aria-label="Primary navigation">
        {isOnProjectPage ? (
          <>
            <button type="button" aria-current="page" onClick={onOpenDrawer}>
              <span className="mobile-nav-symbol">
                <KanbanIcon weight="fill" />
              </span>
              <span>Projects</span>
            </button>
            <button
              type="button"
              onClick={() => onMobileTabChange?.('workspaces')}
            >
              <span className="mobile-nav-symbol">
                <LayoutIcon />
              </span>
              <span>Workspaces</span>
            </button>
          </>
        ) : (
          primaryTabs.map((tab) => {
            const TabIcon = tab.icon;
            const active = mobileActiveTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                aria-current={active ? 'page' : undefined}
                onClick={() => onMobileTabChange?.(tab.id)}
              >
                <span className="mobile-nav-symbol">
                  <TabIcon weight={active ? 'fill' : 'regular'} />
                </span>
                <span>{tab.label}</span>
              </button>
            );
          })
        )}
        <button
          type="button"
          aria-expanded={moreOpen}
          aria-haspopup="dialog"
          aria-current={
            isSecondaryActive && !isOnProjectPage ? 'page' : undefined
          }
          onClick={onOpenMobileMore}
        >
          <span className="mobile-nav-symbol">
            <DotsThreeIcon weight="bold" />
          </span>
          <span>More</span>
        </button>
      </nav>
    );
    return (
      <>
        <header
          className={cn(
            'mobile-app-header bg-secondary border-b shrink-0',
            className
          )}
        >
          <div className="flex items-center min-w-0 gap-half">
            {(isOnProjectSubRoute || mobileShowBack) && onNavigateBack ? (
              <button type="button" onClick={onNavigateBack} aria-label="Back">
                <CaretLeftIcon className="size-icon-lg" />
              </button>
            ) : (
              onOpenDrawer && (
                <button
                  type="button"
                  onClick={onOpenDrawer}
                  aria-label="Projects"
                >
                  <SidebarSimpleIcon className="size-icon-lg" />
                </button>
              )
            )}
            <div className="min-w-0 flex-1">
              <p className="text-lg text-high font-medium truncate">
                {workspaceTitle || (isOnProjectPage ? 'Project' : 'Workspaces')}
              </p>
              {!isOnProjectPage && breadcrumbs && breadcrumbs.length > 0 && (
                <NavbarBreadcrumbs
                  breadcrumbs={breadcrumbs}
                  textClassName="text-sm"
                />
              )}
              {leftSlot}
            </div>
            <SyncErrorIndicator errors={syncErrors} />
          </div>
        </header>
        {showMobileTabs !== false &&
          (navigationSlot
            ? createPortal(navigation, navigationSlot)
            : navigation)}
        <MobileDrawer
          open={moreOpen}
          onClose={() => onCloseMobileMore?.()}
          title="Workspace tools"
        >
          <div className="mobile-tool-sheet p-4">
            {isOnProjectPage &&
              rightItems
                .filter((item): item is NavbarActionItem => !isDivider(item))
                .map((item) => {
                  const ItemIcon = item.icon;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      disabled={item.disabled}
                      onClick={() => runMoreAction(() => item.onClick?.())}
                    >
                      <ItemIcon className="size-icon-lg" />
                      <span>{item.tooltip ?? item.id}</span>
                    </button>
                  );
                })}
            {!isOnProjectPage &&
              secondaryTabs.map((tab) => {
                const TabIcon = tab.icon;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    aria-pressed={mobileActiveTab === tab.id}
                    onClick={() =>
                      runMoreAction(() => onMobileTabChange?.(tab.id))
                    }
                  >
                    <TabIcon className="size-icon-lg" />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            {onNavigateToBoard && (
              <button
                type="button"
                onClick={() => runMoreAction(onNavigateToBoard)}
              >
                <KanbanIcon className="size-icon-lg" />
                <span>Project board</span>
              </button>
            )}
            {!isOnProjectPage && onOpenCommandBar && (
              <button
                type="button"
                onClick={() => runMoreAction(onOpenCommandBar)}
              >
                <ListIcon className="size-icon-lg" />
                <span>Actions</span>
              </button>
            )}
            {!isOnProjectPage && onOpenSettings && (
              <button
                type="button"
                onClick={() => runMoreAction(onOpenSettings)}
              >
                <GearIcon className="size-icon-lg" />
                <span>Settings</span>
              </button>
            )}
            {onReload && (
              <button type="button" onClick={onReload}>
                <span>Reload</span>
              </button>
            )}
            {mobileUserSlot}
          </div>
        </MobileDrawer>
      </>
    );
  }

  // ---- Desktop layout ----
  // data-tauri-drag-region must be on every non-interactive element for Tauri 2
  // window dragging to work (the attribute does not propagate to children).
  return (
    <nav
      data-tauri-drag-region
      className={cn(
        'flex items-center justify-between px-base py-half bg-secondary border-b shrink-0',
        className
      )}
    >
      {/* Left - Archive & Old UI Link + optional slot */}
      <div data-tauri-drag-region className="flex-1 flex items-center gap-base">
        {leftItems.map((item, index) =>
          renderItem(
            item,
            `left-${isDivider(item) ? 'divider' : item.id}-${index}`
          )
        )}
        {leftSlot}
      </div>

      {/* Center - Breadcrumbs or Workspace Title */}
      <div className="flex-1 flex items-center justify-center min-w-0">
        {breadcrumbs && breadcrumbs.length > 0 ? (
          <NavbarBreadcrumbs
            breadcrumbs={breadcrumbs}
            textClassName="text-base"
          />
        ) : (
          <p
            className="text-base text-low truncate cursor-text select-text"
            title={workspaceTitle ?? undefined}
          >
            {workspaceTitle ?? ''}
          </p>
        )}
      </div>

      {/* Right - Sync Error Indicator + Diff Controls + Panel Toggles (dividers inline) */}
      <div
        data-tauri-drag-region
        className="flex-1 flex items-center justify-end gap-base"
      >
        <SyncErrorIndicator errors={syncErrors} />
        {rightItems.map((item, index) =>
          renderItem(
            item,
            `right-${isDivider(item) ? 'divider' : item.id}-${index}`
          )
        )}
      </div>
    </nav>
  );
}

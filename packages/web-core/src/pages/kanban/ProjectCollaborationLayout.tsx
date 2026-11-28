import {
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react';
import { useIsMobile } from '@/shared/hooks/useIsMobile';
import { useMobileSheet } from '@/shared/hooks/useMobileSheet';
import { useDotProjectNotifications } from '@/shared/hooks/useDotNotifications';
import { DotActivityIndicators } from '@vibe/ui/components/DotActivityIndicators';
import { ProjectCollaborationSidebar } from './ProjectCollaborationSidebar';
import { ProjectCollaborationPane } from './ProjectCollaborationPane';
import {
  getProjectChatRequest,
  subscribeProjectChatRequest,
  consumeProjectChatRequest,
} from '@/shared/lib/dotProjectNotices';

export function ProjectCollaborationLayout({
  projectId,
  projectName,
  workspaceId,
  issueId,
  children,
}: {
  projectId: string;
  projectName: string;
  workspaceId?: string | null;
  issueId?: string | null;
  children: ReactNode;
}) {
  const [chatWidth, setChatWidth] = useState(420);
  const [fullChat, setFullChat] = useState(false);
  const isMobile = useIsMobile();
  const [desktopOpen, setDesktopOpen] = useState(true);
  const [chatRequest, setChatRequest] = useState(0);
  const projectChatRequest = useSyncExternalStore(
    subscribeProjectChatRequest,
    getProjectChatRequest
  );
  const sheet = useMobileSheet('project-collaboration:' + projectId);
  const closeSheet = sheet.close;
  const showSheet = sheet.show;
  useEffect(() => {
    if (
      !projectChatRequest ||
      projectChatRequest.projectId !== projectId ||
      workspaceId ||
      issueId
    )
      return;
    consumeProjectChatRequest(projectChatRequest);
    setChatRequest(projectChatRequest.sequence);
    setDesktopOpen(true);
    if (isMobile && !sheet.isOpen) showSheet();
  }, [
    projectChatRequest,
    projectId,
    workspaceId,
    issueId,
    isMobile,
    sheet.isOpen,
    showSheet,
  ]);
  const open = isMobile ? sheet.isOpen : desktopOpen;
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const notifications = useDotProjectNotifications();
  const activity = notifications.find((item) => item.project_id === projectId);
  const close = () => {
    if (isMobile) sheet.close();
    else setDesktopOpen(false);
  };
  useEffect(() => {
    if (!isMobile || !open) return;
    const root = panel.current;
    const focusTrigger = trigger.current;
    root?.querySelector<HTMLButtonElement>('button')?.focus();
    const keyboard = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeSheet();
      }
      if (event.key !== 'Tab' || !root) return;
      const nodes = Array.from(
        root.querySelectorAll<HTMLElement>(
          'button, input, textarea, select, [tabindex="0"]'
        )
      ).filter(
        (node) =>
          !node.hasAttribute('disabled') && node.getClientRects().length > 0
      );
      const first = nodes[0],
        last = nodes[nodes.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener('keydown', keyboard);
    return () => {
      document.removeEventListener('keydown', keyboard);
      focusTrigger?.focus();
    };
  }, [isMobile, open, closeSheet]);
  return (
    <div className="project-space-layout">
      <div
        className="project-space-toolbar bg-primary text-normal"
        {...(isMobile && open ? { inert: '' } : {})}
      >
        <span className="truncate">{projectName}</span>
        <button
          ref={trigger}
          type="button"
          aria-label="Open project sidebar"
          aria-expanded={open}
          onClick={() => {
            if (isMobile) sheet.show();
            else setDesktopOpen((value) => !value);
          }}
        >
          Project space{' '}
          <DotActivityIndicators
            dotUnreadCount={activity?.unread_count ?? 0}
            dotNeedsAttentionCount={activity?.needs_attention_count ?? 0}
          />
        </button>
      </div>
      <div className="project-space-body">
        <div
          className="project-space-board"
          hidden={!isMobile && open && fullChat}
          {...(isMobile && open ? { inert: '' } : {})}
        >
          {children}
        </div>
        {open && (
          <ProjectCollaborationPane
            panelRef={panel}
            mobile={isMobile}
            width={chatWidth}
            full={fullChat}
            onWidth={setChatWidth}
            onFull={setFullChat}
          >
            <ProjectCollaborationSidebar
              key={projectId}
              projectId={projectId}
              projectName={projectName}
              workspaceId={workspaceId}
              issueId={issueId}
              chatRequest={chatRequest}
              onClose={close}
              onNavigate={(action) => {
                if (isMobile) sheet.run(action);
                else action();
              }}
            />
          </ProjectCollaborationPane>
        )}
      </div>
    </div>
  );
}

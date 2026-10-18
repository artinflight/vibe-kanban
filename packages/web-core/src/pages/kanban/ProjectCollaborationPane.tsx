import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react';

export function projectChatWidth(width: number, available: number) {
  const min = Math.min(320, available);
  const max = Math.min(available, Math.max(min, available - 320));
  return Math.max(min, Math.min(max, width));
}

/** Size changes keep the same subtree mounted, including chat navigation state. */
export function ProjectCollaborationPane({
  panelRef,
  mobile,
  width,
  full,
  onWidth,
  onFull,
  children,
}: {
  panelRef: RefObject<HTMLDivElement>;
  mobile: boolean;
  width: number;
  full: boolean;
  onWidth: (width: number) => void;
  onFull: (full: boolean) => void;
  children: ReactNode;
}) {
  const [available, setAvailable] = useState(window.innerWidth);
  const drag = useRef<{ x: number; width: number } | null>(null);
  useEffect(() => {
    const parent = panelRef.current?.parentElement;
    if (!parent) return;
    const measure = () => setAvailable(parent.getBoundingClientRect().width);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(parent);
    return () => observer.disconnect();
  }, [panelRef]);
  const current = projectChatWidth(width, available);
  const minimum = projectChatWidth(0, available);
  const maximum = projectChatWidth(Infinity, available);
  return (
    <div
      ref={panelRef}
      className={mobile ? 'project-space-mobile' : 'project-space-sidebar'}
      style={{ width: mobile || full ? '100%' : current }}
      role={mobile ? 'dialog' : undefined}
      aria-modal={mobile ? true : undefined}
      aria-label={mobile ? 'Project collaboration' : undefined}
      data-full-width={full || undefined}
    >
      {!mobile && !full && (
        <div
          className="dot-resize-handle"
          role="separator"
          tabIndex={0}
          aria-label="Resize project sidebar"
          aria-orientation="vertical"
          aria-valuemin={Math.round(minimum)}
          aria-valuemax={Math.round(maximum)}
          aria-valuenow={Math.round(current)}
          onKeyDown={(event) => {
            const next =
              event.key === 'ArrowLeft'
                ? current + 24
                : event.key === 'ArrowRight'
                  ? current - 24
                  : event.key === 'Home'
                    ? minimum
                    : event.key === 'End'
                      ? maximum
                      : null;
            if (next === null) return;
            event.preventDefault();
            onWidth(projectChatWidth(next, available));
          }}
          onPointerDown={(event) => {
            if (event.button !== 0) return;
            event.preventDefault();
            event.currentTarget.focus();
            event.currentTarget.setPointerCapture(event.pointerId);
            drag.current = { x: event.clientX, width: current };
          }}
          onPointerMove={(event) => {
            if (drag.current)
              onWidth(
                projectChatWidth(
                  drag.current.width + drag.current.x - event.clientX,
                  available
                )
              );
          }}
          onPointerUp={(event) => {
            drag.current = null;
            event.currentTarget.releasePointerCapture(event.pointerId);
          }}
          onPointerCancel={() => {
            drag.current = null;
          }}
          onLostPointerCapture={() => {
            drag.current = null;
          }}
        />
      )}
      {!mobile && (
        <div className="project-chat-size-tools">
          <button
            type="button"
            aria-pressed={full}
            onClick={() => onFull(!full)}
          >
            {full ? 'Restore sidebar width' : 'Full-width chat'}
          </button>
        </div>
      )}
      {children}
    </div>
  );
}

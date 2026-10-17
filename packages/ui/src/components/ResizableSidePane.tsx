import { type ReactNode, useEffect, useRef, useState } from 'react';

const KEY = 'vk-dot-prototype-sidebar-width';
export function ResizableSidePane({
  children,
  enabled = true,
}: {
  children: ReactNode;
  enabled?: boolean;
}) {
  const root = useRef<HTMLElement>(null);
  const [width, setWidth] = useState(() => {
    try {
      return Math.max(
        360,
        Math.min(640, Number(localStorage.getItem(KEY)) || 440)
      );
    } catch {
      return 440;
    }
  });
  const [maximum, setMaximum] = useState(640);
  useEffect(() => {
    const update = () =>
      setMaximum(Math.max(280, Math.min(640, window.innerWidth - 480)));
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);
  useEffect(() => {
    try {
      if (enabled) localStorage.setItem(KEY, String(width));
    } catch {
      /* Optional UI preference. */
    }
  }, [width, enabled]);
  const actual = Math.min(width, maximum);
  if (!enabled)
    return (
      <div className="w-[300px] shrink-0 h-full overflow-hidden">
        {children}
      </div>
    );
  return (
    <aside
      ref={root}
      className="dot-resizable-pane"
      style={{ width: actual, maxWidth: '100%' }}
      aria-label="Workspace details"
    >
      <div
        className="dot-resize-handle"
        role="separator"
        tabIndex={0}
        aria-label="Resize details sidebar"
        aria-orientation="vertical"
        aria-valuemin={Math.min(360, maximum)}
        aria-valuemax={maximum}
        aria-valuenow={actual}
        onKeyDown={(event) => {
          if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            setWidth(
              Math.max(
                Math.min(360, maximum),
                Math.min(
                  maximum,
                  actual + (event.key === 'ArrowLeft' ? 20 : -20)
                )
              )
            );
          }
        }}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (
            event.currentTarget.hasPointerCapture(event.pointerId) &&
            root.current
          ) {
            setWidth(
              Math.max(
                Math.min(360, maximum),
                Math.min(
                  maximum,
                  root.current.getBoundingClientRect().right - event.clientX
                )
              )
            );
          }
        }}
        onPointerUp={(event) => {
          if (event.currentTarget.hasPointerCapture(event.pointerId))
            event.currentTarget.releasePointerCapture(event.pointerId);
        }}
      />
      {children}
    </aside>
  );
}

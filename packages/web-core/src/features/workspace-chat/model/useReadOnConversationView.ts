import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react';
import { useWorkspaceSeenAction } from '@/shared/hooks/useWorkspaceSeenAction';
import { WORKSPACE_READ_INTENT } from '@/shared/lib/workspaceReadIntent';

type ReadView = {
  workspaceId: string;
  sessionId: string | undefined;
  ready: boolean;
  replyKey: string | undefined;
  revision: string | undefined;
  scrollRef: RefObject<HTMLDivElement>;
  revealLatest: () => void;
};

function foreground() {
  return document.visibilityState === 'visible' && document.hasFocus();
}

function displayed(root: HTMLElement) {
  if (root.getClientRects().length === 0) return false;
  for (let node: HTMLElement | null = root; node; node = node.parentElement) {
    const style = getComputedStyle(node);
    if (
      node.hidden ||
      node.hasAttribute('inert') ||
      node.getAttribute('aria-hidden') === 'true' ||
      style.display === 'none' ||
      style.visibility === 'hidden' ||
      style.opacity === '0'
    )
      return false;
  }
  return true;
}

/** A navigation/reading gesture may acknowledge visible content once.
 * Polling, layout changes and tab return can only recheck an existing intent;
 * hiding/blurring cancels it. A newer reply invalidates the captured revision.
 */
export function useReadOnConversationView(view: ReadView) {
  const markSeen = useWorkspaceSeenAction();
  const latest = useRef(view);
  const refresh = useRef<() => void>(() => {});
  useLayoutEffect(() => {
    latest.current = view;
  });

  useEffect(() => {
    if (!view.sessionId) return;
    const root = view.scrollRef.current;
    if (!root) return;
    let intent: { revision: string | undefined } | null = foreground()
      ? { revision: undefined }
      : null;
    let inFlight = false;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let wasDisplayed = displayed(root);
    const cancel = () => {
      intent = null;
      if (timer) clearTimeout(timer);
      timer = undefined;
    };
    const eligible = () => {
      const current = latest.current;
      if (!intent || !current.ready || !current.replyKey || !current.revision)
        return false;
      if (intent.revision === undefined) intent.revision = current.revision;
      if (intent.revision !== current.revision) {
        cancel();
        return false;
      }
      if (!foreground() || !displayed(root)) return false;
      const node = Array.from(
        root.querySelectorAll<HTMLElement>('[data-workspace-read-reply]')
      ).find((node) => node.dataset.workspaceReadReply === current.replyKey);
      if (!node || node.getClientRects().length === 0) return false;
      const bounds = root.getBoundingClientRect();
      const reply = node.getBoundingClientRect();
      const viewport = window.visualViewport;
      const top = Math.max(bounds.top, viewport?.offsetTop ?? 0, 0);
      const bottom = Math.min(
        bounds.bottom,
        window.innerHeight,
        viewport ? viewport.offsetTop + viewport.height : window.innerHeight
      );
      if (
        reply.width <= 0 ||
        reply.height <= 0 ||
        reply.bottom <= top ||
        reply.bottom > bottom ||
        reply.right <= Math.max(0, bounds.left) ||
        reply.left >= Math.min(window.innerWidth, bounds.right)
      )
        return false;
      // Avoid acknowledging a reply covered by another panel/dialog.
      if (typeof document.elementFromPoint === 'function') {
        const x =
          (Math.max(reply.left, bounds.left, 0) +
            Math.min(reply.right, bounds.right, window.innerWidth)) /
          2;
        const hit = document.elementFromPoint(x, reply.bottom - 1);
        if (!hit || !node.contains(hit)) return false;
      }
      return true;
    };
    const check = () => {
      if (disposed || inFlight) return;
      const visible = displayed(root);
      if (visible && !wasDisplayed && foreground()) {
        intent = {
          revision: latest.current.ready ? latest.current.revision : undefined,
        };
      }
      wasDisplayed = visible;
      if (!eligible()) {
        if (timer) clearTimeout(timer);
        timer = undefined;
        return;
      }
      if (timer) return;
      timer = setTimeout(() => {
        timer = undefined;
        if (disposed || !eligible()) return;
        intent = null;
        inFlight = true;
        void markSeen(view.workspaceId)
          .catch((error) =>
            console.warn('Failed to mark displayed replies read:', error)
          )
          .finally(() => {
            inFlight = false;
          });
      }, 350);
    };
    const arm = () => {
      if (!foreground() || !displayed(root) || inFlight) return;
      intent = {
        revision: latest.current.ready ? latest.current.revision : undefined,
      };
      check();
    };
    const reselect = (event: Event) => {
      if (
        (event as CustomEvent<{ workspaceId: string }>).detail?.workspaceId !==
        view.workspaceId
      )
        return;
      if (!foreground() || !displayed(root)) return;
      latest.current.revealLatest();
      arm();
    };
    const keydown = (event: KeyboardEvent) => {
      if (
        ['ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'End', ' '].includes(
          event.key
        )
      )
        arm();
    };
    const visibility = () => {
      if (!foreground()) cancel();
    };
    refresh.current = check;
    root.addEventListener('scroll', check, { passive: true });
    root.addEventListener('wheel', arm, { passive: true });
    root.addEventListener('pointerdown', arm);
    root.addEventListener('touchstart', arm, { passive: true });
    root.addEventListener('keydown', keydown);
    window.addEventListener(WORKSPACE_READ_INTENT, reselect);
    window.addEventListener('blur', cancel);
    document.addEventListener('visibilitychange', visibility);
    const resize =
      typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(check);
    resize?.observe(root);
    if (root.firstElementChild) resize?.observe(root.firstElementChild);
    const mutation =
      typeof MutationObserver === 'undefined'
        ? null
        : new MutationObserver(check);
    for (let node: HTMLElement | null = root; node; node = node.parentElement) {
      mutation?.observe(node, {
        attributes: true,
        attributeFilter: ['class', 'style', 'hidden', 'inert', 'aria-hidden'],
      });
    }
    check();
    return () => {
      disposed = true;
      cancel();
      refresh.current = () => {};
      resize?.disconnect();
      mutation?.disconnect();
      root.removeEventListener('scroll', check);
      root.removeEventListener('wheel', arm);
      root.removeEventListener('pointerdown', arm);
      root.removeEventListener('touchstart', arm);
      root.removeEventListener('keydown', keydown);
      window.removeEventListener(WORKSPACE_READ_INTENT, reselect);
      window.removeEventListener('blur', cancel);
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [view.workspaceId, view.sessionId, view.scrollRef, markSeen]);

  useEffect(() => {
    refresh.current();
  }, [view.ready, view.replyKey, view.revision]);
}

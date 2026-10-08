import { useLayoutEffect, type RefObject } from 'react';

/** Fit the application to the visible viewport, including browsers that pan
 * rather than resize their layout viewport when the software keyboard opens.
 * Pinch zoom remains browser-owned; it must not reflow the application. */
export function useMobileViewport(
  ref: RefObject<HTMLElement>,
  enabled: boolean
) {
  useLayoutEffect(() => {
    const element = ref.current;
    if (!enabled || !element) return;
    const viewport = window.visualViewport;
    const update = () => {
      if (viewport && viewport.scale !== 1) return;
      const height = viewport?.height ?? window.innerHeight;
      document.documentElement.style.setProperty(
        '--mobile-viewport-height',
        `${height}px`
      );
      document.documentElement.style.setProperty(
        '--mobile-viewport-top',
        `${viewport?.offsetTop ?? 0}px`
      );
      element.style.height = `${height}px`;
      element.style.top = `${viewport?.offsetTop ?? 0}px`;
      const focused = document.activeElement;
      const editing =
        focused instanceof HTMLElement &&
        (focused.isContentEditable || focused.matches('input, textarea'));
      element.dataset.keyboardOpen = String(
        editing && window.innerHeight - height > 150
      );
    };
    const updateAfterFocus = () => queueMicrotask(update);
    update();
    viewport?.addEventListener('resize', update);
    viewport?.addEventListener('scroll', update);
    window.addEventListener('resize', update);
    document.addEventListener('focusin', updateAfterFocus);
    document.addEventListener('focusout', updateAfterFocus);
    return () => {
      viewport?.removeEventListener('resize', update);
      viewport?.removeEventListener('scroll', update);
      window.removeEventListener('resize', update);
      document.removeEventListener('focusin', updateAfterFocus);
      document.removeEventListener('focusout', updateAfterFocus);
      element.style.removeProperty('height');
      element.style.removeProperty('top');
      delete element.dataset.keyboardOpen;
      document.documentElement.style.removeProperty('--mobile-viewport-height');
      document.documentElement.style.removeProperty('--mobile-viewport-top');
    };
  }, [enabled, ref]);
}

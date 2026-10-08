import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import { useRouter } from '@tanstack/react-router';

/** A sheet is one navigation step. Android/browser Back dismisses it before
 * leaving the screen; selecting an item consumes that step before navigation. */
export function useMobileSheet(name: string) {
  const { history } = useRouter();
  const pending = useRef<(() => void) | null>(null);
  const isOpen = useSyncExternalStore(
    useCallback((notify) => history.subscribe(notify), [history]),
    () =>
      (history.location.state as { mobileSheet?: string }).mobileSheet === name
  );

  useEffect(
    () =>
      history.subscribe(() => {
        if (
          (history.location.state as { mobileSheet?: string }).mobileSheet !==
            name &&
          pending.current
        ) {
          const action = pending.current;
          pending.current = null;
          action();
        }
      }),
    [history, name]
  );

  useEffect(
    () => () => {
      pending.current = null;
    },
    []
  );

  const show = useCallback(() => {
    history.push(history.location.href, {
      ...history.location.state,
      mobileSheet: name,
    });
  }, [history, name]);

  const close = useCallback(() => {
    if (isOpen) history.back();
  }, [history, isOpen]);

  const run = useCallback(
    (action: () => void) => {
      if (!isOpen) {
        action();
        return;
      }
      pending.current = action;
      history.back();
    },
    [history, isOpen]
  );

  return { isOpen, show, close, run };
}

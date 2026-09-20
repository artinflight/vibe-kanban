import { useEffect, useLayoutEffect, useRef } from 'react';

/** Resume at the latest output on navigation or return from a background tab. */
export function useResumeConversationAtBottom(
  scopeKey: string,
  resumeAtBottom: () => void
) {
  const resumeRef = useRef(resumeAtBottom);
  useLayoutEffect(() => {
    resumeRef.current = resumeAtBottom;
  });

  useLayoutEffect(() => {
    resumeRef.current();
  }, [scopeKey]);

  useEffect(() => {
    const resume = () => {
      if (document.visibilityState === 'visible') resumeRef.current();
    };
    document.addEventListener('visibilitychange', resume);
    window.addEventListener('pageshow', resume);
    return () => {
      document.removeEventListener('visibilitychange', resume);
      window.removeEventListener('pageshow', resume);
    };
  }, []);
}

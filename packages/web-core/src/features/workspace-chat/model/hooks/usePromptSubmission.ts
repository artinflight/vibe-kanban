import { useCallback, useRef, useState } from 'react';

/** Share one admission guard across Send and active-turn follow-up, including
 * draft persistence/cleanup. State alone cannot guard calls before rerender. */
export function usePromptSubmission() {
  const pending = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const submit = useCallback(async (action: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    setIsSubmitting(true);
    try {
      await action();
    } finally {
      pending.current = false;
      setIsSubmitting(false);
    }
  }, []);
  return { submit, isSubmitting };
}

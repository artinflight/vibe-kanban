import { useCallback, useEffect, useState } from 'react';

// The layout owns this handoff: the composer/sidebar may unmount before the
// router arrives, and a persisted local issue may precede its collection refresh.
export function useExpectedIssueOpen(
  scope: string,
  issueId: string | null,
  hasIssue: (id: string) => boolean
) {
  const [expected, setExpected] = useState<{
    scope: string;
    id: string;
    origin: string | null;
    arrived: boolean;
  } | null>(null);
  const markExpectedIssue = useCallback(
    (id: string) => setExpected({ scope, id, origin: issueId, arrived: false }),
    [scope, issueId]
  );

  useEffect(() => {
    if (!expected) return;
    if (
      expected.scope !== scope ||
      (issueId === expected.id && hasIssue(expected.id)) ||
      (issueId !== expected.id &&
        (expected.arrived || issueId !== expected.origin))
    ) {
      setExpected(null);
    } else if (issueId === expected.id && !expected.arrived) {
      setExpected({ ...expected, arrived: true });
    }
  }, [expected, scope, issueId, hasIssue]);

  return {
    expectedIssueId: expected?.scope === scope ? expected.id : null,
    markExpectedIssue,
  };
}

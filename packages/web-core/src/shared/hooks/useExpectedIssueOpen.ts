import { useCallback, useEffect } from 'react';
import { create } from 'zustand';

export const useExpectedIssueOpenStore = create<{
  expected: {
    scope: string;
    id: string;
    origin: string | null;
    arrived: boolean;
  } | null;
}>(() => ({ expected: null }));

// Flat project/issue routes remount the layout as well as the composer/sidebar.
// Keep the handoff in browser memory until route arrival and collection refresh.
export function useExpectedIssueOpen(
  scope: string,
  issueId: string | null,
  hasIssue: (id: string) => boolean
) {
  const expected = useExpectedIssueOpenStore((state) => state.expected);
  const markExpectedIssue = useCallback(
    (id: string) =>
      useExpectedIssueOpenStore.setState({
        expected: { scope, id, origin: issueId, arrived: false },
      }),
    [scope, issueId]
  );

  useEffect(() => {
    if (!expected || useExpectedIssueOpenStore.getState().expected !== expected)
      return;
    if (
      expected.scope !== scope ||
      (issueId === expected.id && hasIssue(expected.id)) ||
      (issueId !== expected.id &&
        (expected.arrived || issueId !== expected.origin))
    ) {
      useExpectedIssueOpenStore.setState({ expected: null });
    } else if (issueId === expected.id && !expected.arrived) {
      useExpectedIssueOpenStore.setState({
        expected: { ...expected, arrived: true },
      });
    }
  }, [expected, scope, issueId, hasIssue]);

  return {
    expectedIssueId: expected?.scope === scope ? expected.id : null,
    markExpectedIssue,
  };
}

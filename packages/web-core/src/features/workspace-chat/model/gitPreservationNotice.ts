import type { NormalizedEntry } from 'shared/types';

const captureReasons = [
  [
    'pending',
    'original heads retained; publication awaits a reviewed repository policy',
  ],
  [
    'pending',
    'completed original heads durably observed; publication admission remains blocked',
  ],
  [
    'blocked',
    'completed-turn observation is unproven; original obligation retained; scoped reconciliation required',
  ],
  ['blocked', 'completion observation has no matching original obligation'],
  ['blocked', 'affected repository inventory differs from admitted turn'],
] as const;

/** Only machine notices for this exact owner; user/assistant text stays intact. */
export function isCapturedGitNotice(
  entry: NormalizedEntry | null,
  workspaceId: string | undefined,
  executionId: string
): boolean {
  if (
    !entry ||
    !workspaceId ||
    !executionId ||
    !['error_message', 'system_message'].includes(entry.entry_type.type)
  )
    return false;
  return captureReasons.some(([state, reason]) => {
    const prefix = `Git preservation ${state}. Workspace: ${workspaceId}. Turn: ${executionId}. ${reason}. Excluded files are not Git-protected.`;
    if (!entry.content.startsWith(prefix)) return false;
    const suffix = entry.content.slice(prefix.length);
    return suffix === '' || suffix.startsWith('\nRepository: ');
  });
}

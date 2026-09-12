import type { PatchType } from 'shared/types';
import type { PatchTypeWithKey } from '@/shared/hooks/useConversationHistory/types';

export interface HistoryPage {
  entries: { index: number; entry: PatchType }[];
  next_before: number | null;
}

/** Preserve absolute log indices so prepending a page never renumbers rows. */
export function mergeHistoryPage(
  processId: string,
  existing: PatchTypeWithKey[],
  page: HistoryPage
): PatchTypeWithKey[] {
  const entries = new Map(existing.map((entry) => [entry.patchKey, entry]));
  for (const { index, entry } of page.entries) {
    const patchKey = `${processId}:${index}`;
    entries.set(patchKey, {
      ...entry,
      patchKey,
      executionProcessId: processId,
    });
  }
  return [...entries.values()].sort(
    (a, b) =>
      Number(a.patchKey.slice(processId.length + 1)) -
      Number(b.patchKey.slice(processId.length + 1))
  );
}

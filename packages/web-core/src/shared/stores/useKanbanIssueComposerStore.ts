import { useCallback } from 'react';
import { create } from 'zustand';
import type { Issue, IssuePriority } from 'shared/remote-types';
import type { IssueFormData } from '@vibe/ui/components/KanbanIssuePanel';
import type { IssueCreationProgress } from '@/shared/lib/issueCreation';

export type KanbanIssueSubmission = IssueCreationProgress<Issue, IssueFormData>;

export interface ProjectIssueCreateOptions {
  statusId?: string;
  priority?: IssuePriority;
  assigneeIds?: string[];
  parentIssueId?: string;
}

export interface KanbanIssueComposerDraft {
  title: string;
  description: string | null;
  statusId?: string;
  priority?: IssuePriority | null;
  assigneeIds?: string[];
  tagIds?: string[];
  createDraftWorkspace?: boolean;
  parentIssueId?: string;
}

export interface KanbanIssueComposerEntry {
  id: string;
  isOpen: boolean;
  initial: KanbanIssueComposerDraft;
  draft: KanbanIssueComposerDraft;
  submission?: KanbanIssueSubmission;
  submissionPending?: boolean;
}

interface KanbanIssueComposerState {
  byKey: Record<string, KanbanIssueComposerEntry | undefined>;
  openComposer: (
    key: string,
    options?: ProjectIssueCreateOptions | null
  ) => void;
  patchComposer: (
    key: string,
    patch: Partial<KanbanIssueComposerDraft>
  ) => void;
  resetComposer: (key: string) => void;
  checkpointSubmission: (
    key: string,
    composerId: string,
    submission: KanbanIssueSubmission
  ) => void;
  beginSubmission: (key: string, composerId: string) => boolean;
  setSubmissionPending: (
    key: string,
    composerId: string,
    pending: boolean
  ) => void;
  finishSubmission: (key: string, composerId: string) => boolean;
  closeComposer: (key: string, composerId?: string) => void;
}

const LOCAL_HOST_SCOPE = 'local';

function normalizeComposerDraft(
  draft: Partial<KanbanIssueComposerDraft>
): KanbanIssueComposerDraft {
  return {
    title: draft.title ?? '',
    description: draft.description ?? null,
    ...(draft.statusId ? { statusId: draft.statusId } : {}),
    ...(draft.priority !== undefined ? { priority: draft.priority } : {}),
    ...(draft.assigneeIds !== undefined
      ? { assigneeIds: [...draft.assigneeIds] }
      : {}),
    ...(draft.tagIds !== undefined ? { tagIds: [...draft.tagIds] } : {}),
    ...(draft.createDraftWorkspace !== undefined
      ? { createDraftWorkspace: draft.createDraftWorkspace }
      : {}),
    ...(draft.parentIssueId ? { parentIssueId: draft.parentIssueId } : {}),
  };
}

export function buildKanbanIssueComposerKey(
  hostId: string | null,
  projectId: string
): string {
  const hostScope = hostId ?? LOCAL_HOST_SCOPE;
  return `${hostScope}:${projectId}`;
}

function toInitialComposerDraft(
  options?: ProjectIssueCreateOptions | null
): KanbanIssueComposerDraft {
  return normalizeComposerDraft({
    statusId: options?.statusId,
    priority: options?.priority,
    assigneeIds: options?.assigneeIds,
    parentIssueId: options?.parentIssueId,
    tagIds: [],
    createDraftWorkspace: false,
  });
}

export const useKanbanIssueComposerStore = create<KanbanIssueComposerState>()(
  (set) => ({
    byKey: {},
    openComposer: (key, options) =>
      set((state) => {
        const current = state.byKey[key];
        if (
          current &&
          (!current.isOpen ||
            current.submission?.issue ||
            current.submissionPending)
        ) {
          return {
            byKey: { ...state.byKey, [key]: { ...current, isOpen: true } },
          };
        }
        const initial = toInitialComposerDraft(options);
        return {
          byKey: {
            ...state.byKey,
            [key]: {
              id: crypto.randomUUID(),
              isOpen: true,
              initial,
              draft: initial,
            },
          },
        };
      }),
    patchComposer: (key, patch) =>
      set((state) => {
        const current = state.byKey[key];
        if (
          !current ||
          current.submission?.issue ||
          current.submissionPending
        ) {
          return state;
        }

        return {
          byKey: {
            ...state.byKey,
            [key]: {
              ...current,
              draft: normalizeComposerDraft({
                ...current.draft,
                ...patch,
              }),
            },
          },
        };
      }),
    resetComposer: (key) =>
      set((state) => {
        const current = state.byKey[key];
        if (
          !current ||
          current.submission?.issue ||
          current.submissionPending
        ) {
          return state;
        }

        return {
          byKey: {
            ...state.byKey,
            [key]: {
              ...current,
              draft: current.initial,
            },
          },
        };
      }),
    checkpointSubmission: (key, composerId, submission) =>
      set((state) => {
        const current = state.byKey[key];
        if (!current || current.id !== composerId) return state;
        return {
          byKey: {
            ...state.byKey,
            [key]: { ...current, submission },
          },
        };
      }),
    beginSubmission: (key, composerId) => {
      let started = false;
      set((state) => {
        const current = state.byKey[key];
        if (
          !current ||
          current.id !== composerId ||
          !current.isOpen ||
          current.submissionPending
        )
          return state;
        started = true;
        return {
          byKey: {
            ...state.byKey,
            [key]: { ...current, submissionPending: true },
          },
        };
      });
      return started;
    },
    setSubmissionPending: (key, composerId, pending) =>
      set((state) => {
        const current = state.byKey[key];
        if (!current || current.id !== composerId) return state;
        return {
          byKey: {
            ...state.byKey,
            [key]: { ...current, submissionPending: pending },
          },
        };
      }),
    finishSubmission: (key, composerId) => {
      let wasOpen = false;
      set((state) => {
        const current = state.byKey[key];
        if (!current || current.id !== composerId) return state;
        wasOpen = current.isOpen;
        const byKey = { ...state.byKey };
        delete byKey[key];
        return { byKey };
      });
      return wasOpen;
    },
    closeComposer: (key, composerId) =>
      set((state) => {
        const current = state.byKey[key];
        if (!current || (composerId && current.id !== composerId)) {
          return state;
        }
        // Dismiss the view without discarding a request or a saved issue.
        if (current.submissionPending || current.submission?.issue) {
          return {
            byKey: { ...state.byKey, [key]: { ...current, isOpen: false } },
          };
        }

        const byKey = { ...state.byKey };
        delete byKey[key];
        return { byKey };
      }),
  })
);

export function useKanbanIssueComposer(
  composerKey: string | null
): KanbanIssueComposerEntry | null {
  return useKanbanIssueComposerStore(
    useCallback(
      (state) => {
        const entry = composerKey ? state.byKey[composerKey] : null;
        return entry?.isOpen ? entry : null;
      },
      [composerKey]
    )
  );
}

export function openKanbanIssueComposer(
  composerKey: string,
  options?: ProjectIssueCreateOptions | null
): void {
  useKanbanIssueComposerStore.getState().openComposer(composerKey, options);
}

export function patchKanbanIssueComposer(
  composerKey: string,
  patch: Partial<KanbanIssueComposerDraft>
): void {
  useKanbanIssueComposerStore.getState().patchComposer(composerKey, patch);
}

export function resetKanbanIssueComposer(composerKey: string): void {
  useKanbanIssueComposerStore.getState().resetComposer(composerKey);
}

export function closeKanbanIssueComposer(
  composerKey: string,
  composerId?: string
): void {
  useKanbanIssueComposerStore.getState().closeComposer(composerKey, composerId);
}

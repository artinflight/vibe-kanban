import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';

export type ReadLaterKind = 'workspace' | 'project' | 'issue' | 'notification';
export type ReadLaterItem = {
  kind: ReadLaterKind;
  id: string;
  name?: string;
  projectId?: string;
};

export const readLaterKey = (scope: string, kind: ReadLaterKind, id: string) =>
  JSON.stringify([scope, kind, id]);

// A separate cache keeps older open tabs from overwriting the sync queue and
// migration markers. Preserve v1 for those tabs; only import its saved choices.
function legacyItems(storageName: string): Record<string, ReadLaterItem> {
  if (storageName !== 'vk-read-later-v2') return {};
  try {
    return (
      JSON.parse(localStorage.getItem('vk-read-later-v1') ?? 'null')?.state
        ?.items ?? {}
    );
  } catch {
    return {};
  }
}

/** A presentation preference only: never writes read/seen/attention state. */
export const createReadLaterStore = (storageName = 'vk-read-later-v2') =>
  create<{
    items: Record<string, ReadLaterItem>;
    pending: Record<
      string,
      { item: ReadLaterItem; later: boolean; changeId: string }
    >;
    migratedScopes: Record<string, boolean>;
    syncErrors: Record<string, string>;
    applyServer: (
      scope: string,
      records: { item: ReadLaterItem; saved: boolean }[]
    ) => void;
    acknowledge: (key: string, changeId: string) => void;
    setReadLater: (scope: string, item: ReadLaterItem, later: boolean) => void;
  }>()(
    persist(
      (set) => ({
        items: legacyItems(storageName),
        pending: {},
        migratedScopes: {},
        syncErrors: {},
        applyServer: (scope, records) =>
          set((state) => {
            const items = Object.fromEntries(
              Object.entries(state.items).filter(
                ([key, item]) => key !== readLaterKey(scope, item.kind, item.id)
              )
            );
            for (const { item, saved } of records)
              if (saved) items[readLaterKey(scope, item.kind, item.id)] = item;
            for (const [key, { item, later }] of Object.entries(
              state.pending
            )) {
              if (key === readLaterKey(scope, item.kind, item.id)) {
                if (later) items[key] = item;
                else delete items[key];
              }
            }
            return { items };
          }),
        acknowledge: (key, changeId) =>
          set((state) => {
            if (state.pending[key]?.changeId !== changeId) return state;
            const pending = { ...state.pending };
            delete pending[key];
            return { pending };
          }),
        setReadLater: (scope, item, later) =>
          set((state) => {
            const items = { ...state.items };
            const key = readLaterKey(scope, item.kind, item.id);
            if (later) items[key] = item;
            else delete items[key];
            return {
              items,
              pending: {
                ...state.pending,
                [key]: {
                  item,
                  later,
                  changeId:
                    globalThis.crypto?.randomUUID?.() ??
                    `${Date.now()}-${Math.random()}`,
                },
              },
            };
          }),
      }),
      {
        name: storageName,
        storage: createJSONStorage(() => ({
          getItem: (key) => {
            try {
              return localStorage.getItem(key);
            } catch {
              return null;
            }
          },
          setItem: (key, value) => {
            try {
              localStorage.setItem(key, value);
            } catch {
              /* Keep the preference in memory. */
            }
          },
          removeItem: (key) => {
            try {
              localStorage.removeItem(key);
            } catch {
              /* Keep the preference in memory. */
            }
          },
        })),
        partialize: ({ items, pending, migratedScopes }) => ({
          items,
          pending,
          migratedScopes,
        }),
      }
    )
  );

export const useReadLaterStore = createReadLaterStore();

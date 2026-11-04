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

/** A presentation preference only: never writes read/seen/attention state. */
export const useReadLaterStore = create<{
  items: Record<string, ReadLaterItem>;
  setReadLater: (scope: string, item: ReadLaterItem, later: boolean) => void;
}>()(
  persist(
    (set) => ({
      items: {},
      setReadLater: (scope, item, later) =>
        set((state) => {
          const items = { ...state.items };
          const key = readLaterKey(scope, item.kind, item.id);
          if (later) items[key] = item;
          else delete items[key];
          return { items };
        }),
    }),
    {
      name: 'vk-read-later-v1',
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
      partialize: ({ items }) => ({ items }),
    }
  )
);

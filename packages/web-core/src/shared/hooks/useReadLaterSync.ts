import { useEffect } from 'react';
import { readLaterApi } from '@/shared/lib/api';
import { ReadLaterSync } from '@/shared/lib/readLater/sync';
import { useReadLaterStore } from '@/shared/stores/useReadLaterStore';

const clients = new Map<
  string,
  { client: ReadLaterSync; users: number; stop?: () => void }
>();
export function readLaterSync(host: string | null, user: string) {
  const scope = JSON.stringify([host ?? 'local', user]);
  let entry = clients.get(scope);
  if (!entry) {
    entry = {
      users: 0,
      client: new ReadLaterSync(
        useReadLaterStore,
        scope,
        {
          list: () => readLaterApi.list(host, user),
          import: (items) => readLaterApi.import(host, user, items),
          set: (item, saved, changeId) =>
            readLaterApi.set(host, user, item, saved, changeId),
        },
        () => navigator.onLine
      ),
    };
    clients.set(scope, entry);
  }
  return entry;
}
export function useReadLaterSync(
  host: string | null,
  user: string,
  enabled: boolean
) {
  useEffect(() => {
    if (!enabled) return;
    const entry = readLaterSync(host, user);
    entry.users++;
    if (entry.users === 1) {
      const refresh = () => {
        if (!document.hidden && navigator.onLine) void entry.client.refresh();
      };
      const timer = window.setInterval(refresh, 5000);
      window.addEventListener('focus', refresh);
      window.addEventListener('pageshow', refresh);
      window.addEventListener('online', refresh);
      const disconnected = () => {
        void entry.client.refresh();
      };
      window.addEventListener('offline', disconnected);
      document.addEventListener('visibilitychange', refresh);
      entry.stop = () => {
        window.clearInterval(timer);
        window.removeEventListener('focus', refresh);
        window.removeEventListener('pageshow', refresh);
        window.removeEventListener('online', refresh);
        window.removeEventListener('offline', disconnected);
        document.removeEventListener('visibilitychange', refresh);
      };
      if (navigator.onLine) refresh();
      else disconnected();
    }
    return () => {
      if (--entry.users === 0) entry.stop?.();
    };
  }, [host, user, enabled]);
}

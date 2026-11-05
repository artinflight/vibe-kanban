import { useCallback, useMemo } from 'react';
import {
  readLaterSync,
  useReadLaterSync,
} from '@/shared/hooks/useReadLaterSync';
import { useHostId } from '@/shared/providers/HostIdProvider';
import { useAuth } from '@/shared/hooks/auth/useAuth';
import {
  readLaterKey,
  useReadLaterStore,
  type ReadLaterItem,
  type ReadLaterKind,
} from '@/shared/stores/useReadLaterStore';

export function useReadLater() {
  const hostId = useHostId();
  const { userId, isLoaded } = useAuth();
  const user = userId ?? 'local';
  useReadLaterSync(hostId, user, isLoaded);
  const scope = JSON.stringify([hostId ?? 'local', userId ?? 'local']);
  const allItems = useReadLaterStore((state) => state.items);
  const items = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(allItems).filter(
          ([key, item]) => key === readLaterKey(scope, item.kind, item.id)
        )
      ),
    [allItems, scope]
  );
  const set = useReadLaterStore((state) => state.setReadLater);
  const isReadLater = useCallback(
    (kind: ReadLaterKind, id: string) => !!items[readLaterKey(scope, kind, id)],
    [items, scope]
  );
  const setReadLater = useCallback(
    (item: ReadLaterItem, later: boolean) => {
      set(scope, item, later);
      if (isLoaded) void readLaterSync(hostId, user).client.refresh();
    },
    [set, scope, isLoaded, hostId, user]
  );
  const syncError = useReadLaterStore((state) => state.syncErrors[scope]);
  return { items, isReadLater, setReadLater, syncError };
}

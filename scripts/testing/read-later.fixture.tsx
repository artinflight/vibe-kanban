import { useSyncExternalStore } from 'react';
import type { GroupedNotification } from '../../packages/web-core/src/shared/lib/notifications';

export const useHostId = () => null;
export const useAuth = () => ({
  userId: 'owner',
  isSignedIn: true,
  isLoaded: true,
});
export const navigations: string[] = [];
export const writes: unknown[] = [];
export const useRouter = () => ({
  navigate: ({ to }: { to: string }) => navigations.push(to),
});
export const useNotificationMembers = () => ({ membersByUserId: new Map() });
export const UserAvatar = () => <span>Avatar</span>;
const listeners = new Set<() => void>();
let groups: GroupedNotification[] = [];
export function setNotifications(value: GroupedNotification[]) {
  groups = value;
  writes.length = 0;
  navigations.length = 0;
  listeners.forEach((notify) => notify());
}
export function useNotifications() {
  const current = useSyncExternalStore(
    (notify) => {
      listeners.add(notify);
      return () => {
        listeners.delete(notify);
      };
    },
    () => groups
  );
  return {
    data: current.map((group) => group.latest),
    groupedNotifications: current,
    updateMany: (value: unknown) => writes.push(value),
    enabled: true,
    unseenCount: current.filter((group) => !group.seen).length,
  };
}

// Component tests isolate synchronization; separate sync tests use two stores.
export const useReadLaterSync = () => {};
export const readLaterSync = () => ({ client: { refresh: async () => {} } });

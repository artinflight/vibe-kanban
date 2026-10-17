import { useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useHostId } from '@/shared/providers/HostIdProvider';

export type DotNotification = {
  project_id: string;
  issue_id: string;
  unread_count: number;
  needs_attention_count: number;
};
export type DotProjectNotification = Omit<DotNotification, 'issue_id'>;
type DotNotifications = {
  issues: DotNotification[];
  projects?: DotProjectNotification[];
};
const EMPTY: DotNotification[] = [];
const EMPTY_SNAPSHOT: DotNotifications = { issues: [] };
export const dotNotificationKey = ['dot-sidechat-notifications'] as const;

// Dot summaries contain no transcript text. Their cookie/CSRF and persistence are
// separate from workspace/agent review state. Unpaired/old services stay quiet.
function useDotNotificationSnapshot() {
  const hostId = useHostId();
  const client = useQueryClient();
  useEffect(() => {
    const changed = (event: Event) => {
      if ((event as CustomEvent<{ reset?: boolean }>).detail?.reset) {
        client.setQueryData([...dotNotificationKey, hostId], EMPTY_SNAPSHOT);
      }
      void client.invalidateQueries({ queryKey: dotNotificationKey });
    };
    window.addEventListener('dot-sidechat-changed', changed);
    return () => window.removeEventListener('dot-sidechat-changed', changed);
  }, [client, hostId]);
  const enabled = import.meta.env.VITE_DOT_SIDECHAT === '1' && !hostId;
  const query = useQuery({
    queryKey: [...dotNotificationKey, hostId],
    queryFn: async ({ signal }) => {
      const response = await fetch('/api/dot-sidechat/notifications', {
        credentials: 'same-origin',
        cache: 'no-store',
        redirect: 'error',
        signal,
        headers: { 'X-Dot-Request': '1' },
      });
      if (!response.ok) return EMPTY_SNAPSHOT;
      return (await response.json()) as DotNotifications;
    },
    enabled,
    staleTime: 1000,
    refetchInterval: 5000,
    refetchOnWindowFocus: true,
    retry: false,
  });
  return enabled ? (query.data ?? EMPTY_SNAPSHOT) : EMPTY_SNAPSHOT;
}

export function useDotNotifications() {
  return useDotNotificationSnapshot().issues ?? EMPTY;
}
export function useDotProjectNotifications(): DotProjectNotification[] {
  return useDotNotificationSnapshot().projects ?? EMPTY;
}

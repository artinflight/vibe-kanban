import { useQuery } from '@tanstack/react-query';
import type { OrganizationMemberWithProfile } from 'shared/types';
import { useAuth } from '@/shared/hooks/auth/useAuth';
import { useUserSystem } from '@/shared/hooks/useUserSystem';

export const LOCAL_PARTICIPANTS_KEY = ['local-participants'] as const;

export function useLocalParticipants() {
  const { loginStatus } = useUserSystem();
  const isLocalOnlySession =
    loginStatus?.status === 'loggedin' && !loginStatus.profile;
  const query = useQuery({
    queryKey: LOCAL_PARTICIPANTS_KEY,
    queryFn: async () => {
      const response = await fetch('/v1/local-participants');
      if (!response.ok) throw new Error('Unable to load local participants');
      return response.json() as Promise<{
        members: OrganizationMemberWithProfile[];
        current_user_id: string;
      }>;
    },
    enabled: isLocalOnlySession,
    staleTime: 60_000,
  });
  return { ...query, isLocalOnlySession };
}

// Assignment identity only; leave authentication and permissions untouched.
export function useAssignmentIdentity() {
  const { userId } = useAuth();
  const participants = useLocalParticipants();
  return participants.isLocalOnlySession
    ? (participants.data?.current_user_id ?? null)
    : userId;
}

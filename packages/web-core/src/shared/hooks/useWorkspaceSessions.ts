import { useQuery } from '@tanstack/react-query';
import { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { sessionsApi } from '@/shared/lib/api';
import { useHostId } from '@/shared/providers/HostIdProvider';
import { workspaceSessionKeys } from '@/shared/hooks/workspaceSessionKeys';
import type { Session } from 'shared/types';

interface UseWorkspaceSessionsOptions {
  enabled?: boolean;
}

/** Discriminated union for session selection state */
export type SessionSelection =
  | { mode: 'existing'; sessionId: string }
  | { mode: 'new' };

interface UseWorkspaceSessionsResult {
  sessions: Session[];
  selectedSession: Session | undefined;
  selectedSessionId: string | undefined;
  selectSession: (sessionId: string) => void;
  selectLatestSession: () => void;
  isLoading: boolean;
  /** Whether user is creating a new session */
  isNewSessionMode: boolean;
  /** Enter new session mode */
  startNewSession: () => void;
}

/**
 * Hook for managing sessions within a workspace.
 * Fetches all sessions for a workspace and provides session switching capability.
 * Sessions are ordered by most recently used (latest non-dev server execution first).
 */
export function useWorkspaceSessions(
  workspaceId: string | undefined,
  options: UseWorkspaceSessionsOptions = {}
): UseWorkspaceSessionsResult {
  const hostId = useHostId();
  const { enabled = true } = options;
  const scope = useMemo(() => ({ hostId, workspaceId }), [hostId, workspaceId]);
  const activeScope = useRef(scope);
  activeScope.current = scope;
  const [selection, setSelection] = useState<{
    scope: typeof scope;
    value: SessionSelection;
  }>();

  const {
    data: sessions = [],
    isLoading,
    isSuccess,
  } = useQuery<Session[]>({
    queryKey: workspaceSessionKeys.byWorkspace(workspaceId, hostId),
    queryFn: async () => {
      const result = await sessionsApi.getByWorkspace(workspaceId!);
      if (result.some((session) => session.workspace_id !== workspaceId)) {
        throw new Error(
          'Session response does not match the selected workspace'
        );
      }
      return result;
    },
    enabled: enabled && !!workspaceId,
  });

  // Derive the current selection during render, before any consumer can send or
  // subscribe. Never expose a previous workspace's session for one effect cycle.
  const currentSelection =
    selection?.scope === scope ? selection.value : undefined;
  const isNewSessionMode =
    isSuccess &&
    enabled &&
    !!workspaceId &&
    (currentSelection?.mode === 'new' || sessions.length === 0);
  const selectedSession = isNewSessionMode
    ? undefined
    : ((currentSelection?.mode === 'existing'
        ? sessions.find((session) => session.id === currentSelection.sessionId)
        : undefined) ?? sessions[0]);
  const selectedSessionId = selectedSession?.id;

  // Pin the initial latest session so a reorder cannot silently change the
  // recipient. Explicit selection of a just-created session can precede refetch.
  useEffect(() => {
    if (!currentSelection && sessions[0]) {
      setSelection({
        scope,
        value: { mode: 'existing', sessionId: sessions[0].id },
      });
    }
  }, [scope, currentSelection, sessions]);

  const updateSelection = useCallback(
    (value: SessionSelection) => {
      // A create/send started in A can finish after navigating to B. Its callback
      // belongs to A and must not select a session or clear a draft in B.
      if (activeScope.current === scope) setSelection({ scope, value });
    },
    [scope]
  );
  const selectSession = useCallback(
    (sessionId: string) => {
      updateSelection({ mode: 'existing', sessionId });
    },
    [updateSelection]
  );
  const selectLatestSession = useCallback(() => {
    if (sessions[0])
      updateSelection({ mode: 'existing', sessionId: sessions[0].id });
  }, [sessions, updateSelection]);
  const startNewSession = useCallback(() => {
    updateSelection({ mode: 'new' });
  }, [updateSelection]);

  return {
    sessions,
    selectedSession,
    selectedSessionId,
    selectSession,
    selectLatestSession,
    isLoading,
    isNewSessionMode,
    startNewSession,
  };
}

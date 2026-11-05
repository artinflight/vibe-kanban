import { useCallback, useMemo } from 'react';
import type { ApprovalInfo } from 'shared/types';
import { useJsonPatchWsStream } from './useJsonPatchWsStream';

interface UseApprovalsResult {
  pendingApprovals: ApprovalInfo[];
  getPendingForProcess: (executionProcessId: string) => ApprovalInfo | null;
  getPendingById: (approvalId: string) => ApprovalInfo | null;
  isConnected: boolean;
}

type ApprovalState = {
  pending: Record<string, ApprovalInfo>;
};

const initialApprovals = (): ApprovalState => ({ pending: {} });

export function useApprovals(): UseApprovalsResult {
  const { data, isConnected, isInitialized } =
    useJsonPatchWsStream<ApprovalState>(
      '/api/approvals/stream/ws',
      true,
      initialApprovals,
      { resetOnReconnect: true, reconnectOnCleanClose: true }
    );

  const pendingById = useMemo(() => data?.pending ?? {}, [data?.pending]);
  const pendingApprovals = useMemo(
    () => Object.values(pendingById),
    [pendingById]
  );

  const getPendingForProcess = useCallback(
    (executionProcessId: string): ApprovalInfo | null => {
      for (const info of pendingApprovals) {
        if (
          info.execution_process_id === executionProcessId &&
          info.tool_name !== 'codex.mcp_approval'
        ) {
          return info;
        }
      }
      return null;
    },
    [pendingApprovals]
  );

  const getPendingById = useCallback(
    (approvalId: string): ApprovalInfo | null => {
      return pendingById[approvalId] ?? null;
    },
    [pendingById]
  );

  return {
    pendingApprovals,
    getPendingForProcess,
    getPendingById,
    isConnected: isConnected && isInitialized,
  };
}

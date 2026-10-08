import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { executionProcessesApi } from '@/shared/lib/api';
import { SubagentJob, SubagentJobStatus } from 'shared/types';

const ACTIVE_SUBAGENT_STATES = new Set<SubagentJobStatus>([
  SubagentJobStatus.unresolved,
  SubagentJobStatus.running,
  SubagentJobStatus.not_found,
]);

type UiSubagentState =
  | 'running'
  | 'unresolved'
  | 'completed'
  | 'not_found'
  | 'failed';

function toUiSubagentState(status: SubagentJobStatus): UiSubagentState {
  switch (status) {
    case SubagentJobStatus.running:
      return 'running';
    case SubagentJobStatus.completed:
      return 'completed';
    case SubagentJobStatus.not_found:
      return 'not_found';
    case SubagentJobStatus.failed:
      return 'failed';
    case SubagentJobStatus.unresolved:
    default:
      return 'unresolved';
  }
}

export function useSubagentJobs(sessionId: string | undefined) {
  const query = useQuery({
    queryKey: ['subagentJobs', sessionId],
    queryFn: () => executionProcessesApi.getSubagentsForSession(sessionId!),
    enabled: !!sessionId,
    retry: false,
    staleTime: 0,
    refetchInterval: (query) => {
      const jobs = query.state.data ?? [];
      return jobs.some((job) => ACTIVE_SUBAGENT_STATES.has(job.status))
        ? 3000
        : false;
    },
    refetchOnWindowFocus: true,
  });

  return useMemo(
    () => ({
      jobs: query.data ?? [],
      isLoading: query.isLoading,
      isBackendAvailable: !query.error,
      refetch: query.refetch,
    }),
    [query.data, query.error, query.isLoading, query.refetch]
  );
}

export function deriveSubagentActivityFromJobs(jobs: SubagentJob[]) {
  const activeCount = jobs.filter(
    (job) => job.status === SubagentJobStatus.running
  ).length;
  const unresolvedCount = jobs.filter(
    (job) => job.status === SubagentJobStatus.unresolved
  ).length;
  const completedCount = jobs.filter(
    (job) => job.status === SubagentJobStatus.completed
  ).length;
  const notFoundCount = jobs.filter(
    (job) => job.status === SubagentJobStatus.not_found
  ).length;

  return {
    activeCount,
    unresolvedCount,
    completedCount,
    notFoundCount,
    items: jobs.map((job) => ({
      id: job.agent_id,
      label: job.nickname
        ? `${job.nickname} (${job.agent_id.slice(0, 8)})`
        : job.agent_id.slice(0, 8),
      state: toUiSubagentState(job.status),
    })),
    shouldConfirmBeforeSend: activeCount + unresolvedCount + notFoundCount > 0,
  };
}

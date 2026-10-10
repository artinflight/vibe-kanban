import {
  ExecutionProcess,
  ExecutionProcessStatus,
  PatchType,
} from 'shared/types';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useExecutionProcessesContext } from '@/shared/hooks/useExecutionProcessesContext';
import { streamJsonPatchEntries } from '@/shared/lib/streamJsonPatchEntries';
import { makeLocalApiRequest } from '@/shared/lib/localApiTransport';
import type {
  AddEntryType,
  ExecutionProcessStateStore,
  UseConversationHistoryParams,
} from '@/shared/hooks/useConversationHistory/types';
import {
  MIN_INITIAL_ENTRIES,
  REMAINING_BATCH_SIZE,
} from '@/shared/hooks/useConversationHistory/constants';
import { mergeHistoryPage, type HistoryPage } from '../historyPage';

export interface UseConversationHistoryResult {
  isFirstTurn: boolean;
  isLoadingHistory: boolean;
  hasMoreHistory: boolean;
  historyError: boolean;
  historyErrorDetail: string | null;
  loadMoreHistory: () => Promise<void>;
}

type Scope = {
  abort: AbortController;
  displayed: ExecutionProcessStateStore;
  // Absent = never fetched, number = next older cursor, null = fully fetched.
  cursors: Map<string, number | null>;
  streams: Map<string, { close: () => void }>;
  statuses: Map<string, ExecutionProcessStatus>;
  emptyEmitted: boolean;
  initialIds: Set<string> | null;
  initialLoaded: boolean;
  loading: boolean;
  pending: Map<string, ReturnType<typeof setTimeout>>;
  errors: Map<string, string | null>;
};

function createScope(): Scope {
  return {
    abort: new AbortController(),
    displayed: {},
    cursors: new Map(),
    streams: new Map(),
    statuses: new Map(),
    emptyEmitted: false,
    initialIds: null,
    initialLoaded: false,
    loading: false,
    pending: new Map(),
    errors: new Map(),
  };
}

// Retry only explicitly draining captures; terminal errors retain manual retry.
const CAPTURE_RETRY_MS = 1000;
class CapturePending extends Error {}

const isRunning = (process: ExecutionProcess) =>
  process.status === ExecutionProcessStatus.running;

export const useConversationHistory = ({
  onTimelineUpdated,
  scopeKey,
}: UseConversationHistoryParams): UseConversationHistoryResult => {
  const {
    executionProcessesVisible: rawProcesses,
    isLoading,
    isConnected,
  } = useExecutionProcessesContext();
  const processes = useMemo(
    () =>
      rawProcesses
        .filter((p) =>
          [
            'setupscript',
            'cleanupscript',
            'archivescript',
            'codingagent',
          ].includes(p.run_reason)
        )
        .sort(
          (a, b) =>
            a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)
        ),
    [rawProcesses]
  );
  const canReadRef = useRef(isConnected && !isLoading);
  canReadRef.current = isConnected && !isLoading;
  const processesRef = useRef(processes);
  processesRef.current = processes;
  const callbackRef = useRef(onTimelineUpdated);
  callbackRef.current = onTimelineUpdated;
  const scopeRef = useRef<Scope>(createScope());
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [hasMoreHistory, setHasMoreHistory] = useState(false);
  const [historyError, setHistoryError] = useState(false);
  const [historyErrorDetail, setHistoryErrorDetail] = useState<string | null>(
    null
  );
  const [revision, setRevision] = useState(0);

  const publishHistoryErrors = useCallback((scope: Scope) => {
    if (scope.abort.signal.aborted) return;
    setHistoryError(scope.errors.size > 0);
    setHistoryErrorDetail(
      [...scope.errors.values()].find((detail) => detail !== null) ?? null
    );
  }, []);

  const recordHistoryError = useCallback(
    (scope: Scope, executionId: string, detail?: string) => {
      if (
        scope.abort.signal.aborted ||
        !processesRef.current.some((p) => p.id === executionId)
      )
        return;
      scope.errors.set(
        executionId,
        detail ?? scope.errors.get(executionId) ?? null
      );
      publishHistoryErrors(scope);
    },
    [publishHistoryErrors]
  );

  const emit = useCallback(
    (scope: Scope, type: AddEntryType, loading = false) => {
      if (scope.abort.signal.aborted) return;
      const latest = Object.values(scope.displayed)
        .sort((a, b) =>
          a.executionProcess.created_at.localeCompare(
            b.executionProcess.created_at
          )
        )
        .at(-1)
        ?.entries.at(-1);
      if (
        type === 'running' &&
        latest?.type === 'NORMALIZED_ENTRY' &&
        latest.content.entry_type.type === 'tool_use' &&
        latest.content.entry_type.tool_name === 'ExitPlanMode'
      )
        type = 'plan';
      callbackRef.current?.(
        {
          executionProcessState: { ...scope.displayed },
          liveExecutionProcesses: processesRef.current,
        },
        type,
        loading
      );
      setHasMoreHistory(
        processesRef.current.some(
          (p) =>
            !isRunning(p) &&
            (!scope.cursors.has(p.id) || scope.cursors.get(p.id) !== null)
        )
      );
    },
    []
  );

  useEffect(() => {
    const scope = createScope();
    scopeRef.current = scope;
    setIsLoadingHistory(false);
    setHistoryError(false);
    setHistoryErrorDetail(null);
    setHasMoreHistory(false);
    emit(scope, 'initial', true);
    return () => {
      scope.abort.abort();
      for (const stream of scope.streams.values()) stream.close();
      for (const timer of scope.pending.values()) clearTimeout(timer);
      scope.pending.clear();
    };
  }, [scopeKey, emit]);

  const fetchPage = useCallback(
    async (
      scope: Scope,
      process: ExecutionProcess,
      limit: number
    ): Promise<number> => {
      const cursor = scope.cursors.get(process.id);
      const query = new URLSearchParams({ limit: String(limit) });
      if (cursor != null) query.set('before', String(cursor));
      const response = await makeLocalApiRequest(
        `/api/execution-processes/${process.id}/log-history?${query}`,
        {
          signal: scope.abort.signal,
        }
      );
      if (
        !response.ok ||
        !response.headers.get('content-type')?.includes('application/json')
      ) {
        throw new Error(`History request failed (${response.status})`);
      }
      const result: { success: boolean; data: HistoryPage } =
        await response.json();
      if (
        scope.abort.signal.aborted ||
        !processesRef.current.some((p) => p.id === process.id)
      )
        return 0;
      if (!result.success || !Array.isArray(result.data?.entries))
        throw new Error('Invalid history page');
      if (result.data.capture_error) {
        const timer = scope.pending.get(process.id);
        if (timer !== undefined) clearTimeout(timer);
        scope.pending.delete(process.id);
        recordHistoryError(
          scope,
          process.id,
          'Capture completeness could not be verified. Earlier messages are not a current status report.'
        );
        throw new Error(result.data.capture_error);
      }
      if (result.data.capture_pending) {
        scope.initialLoaded = true;
        setIsLoadingHistory(true);
        // One timer per execution. Re-read the authoritative finite API after
        // one second; never infer closure from Completed or websocket EOF.
        if (!scope.pending.has(process.id)) {
          const retry = () => {
            scope.pending.delete(process.id);
            if (scope.abort.signal.aborted) return;
            const current = processesRef.current.find(
              (p) => p.id === process.id
            );
            if (!current || isRunning(current)) {
              setIsLoadingHistory(scope.pending.size > 0);
              return;
            }
            if (!canReadRef.current) {
              scope.pending.set(
                process.id,
                setTimeout(retry, CAPTURE_RETRY_MS)
              );
              return;
            }
            void fetchPage(scope, current, limit)
              .then(() => {
                if (scope.abort.signal.aborted) return;
                setIsLoadingHistory(scope.pending.size > 0);
                emit(scope, 'running');
              })
              .catch((error) => {
                if (
                  scope.abort.signal.aborted ||
                  error instanceof CapturePending
                )
                  return;
                setIsLoadingHistory(scope.pending.size > 0);
                recordHistoryError(scope, process.id);
              });
          };
          scope.pending.set(process.id, setTimeout(retry, CAPTURE_RETRY_MS));
        }
        throw new CapturePending('Capture is still draining');
      }
      const timer = scope.pending.get(process.id);
      if (timer !== undefined) clearTimeout(timer);
      scope.pending.delete(process.id);
      scope.displayed[process.id] = {
        executionProcess: process,
        entries: mergeHistoryPage(
          process.id,
          scope.displayed[process.id]?.entries ?? [],
          result.data
        ),
      };
      scope.cursors.set(process.id, result.data.next_before);
      // An authoritative successful page resolves only this execution's error.
      // Other completed turns may still have unavailable or damaged captures.
      scope.errors.delete(process.id);
      publishHistoryErrors(scope);
      return result.data.entries.length;
    },
    [emit, publishHistoryErrors, recordHistoryError]
  );

  const loadBatch = useCallback(
    async (scope: Scope, initial: boolean) => {
      // A ref lock also covers multiple scroll events before React has rendered.
      if (scope.loading || scope.abort.signal.aborted) return;
      scope.loading = true;
      scope.initialIds ??= new Set(processesRef.current.map((p) => p.id));
      setIsLoadingHistory(true);
      let fetchingId: string | null = null;
      try {
        let remaining = initial ? MIN_INITIAL_ENTRIES : REMAINING_BATCH_SIZE;
        for (const process of [...processesRef.current].reverse()) {
          if (scope.abort.signal.aborted) return;
          if (isRunning(process) || scope.cursors.get(process.id) === null)
            continue;
          fetchingId = process.id;
          remaining -= await fetchPage(scope, process, remaining);
          if (remaining <= 0) break;
        }
        scope.initialLoaded = true;
        emit(scope, initial ? 'initial' : 'historic');
      } catch (error) {
        if (!scope.abort.signal.aborted) {
          if (!(error instanceof CapturePending)) {
            console.warn('Unable to load conversation history', error);
            if (fetchingId !== null) recordHistoryError(scope, fetchingId);
          }
          // Keep successfully loaded pages visible and let the user retry.
          emit(scope, initial ? 'initial' : 'historic');
        }
      } finally {
        scope.loading = false;
        if (!scope.abort.signal.aborted) {
          setIsLoadingHistory(scope.pending.size > 0);
          setRevision((value) => value + 1);
        }
      }
    },
    [emit, fetchPage, recordHistoryError]
  );

  useEffect(() => {
    if (isLoading || !isConnected) return;
    const scope = scopeRef.current;
    const ids = new Set(processes.map((p) => p.id));
    let errorsRemoved = false;
    for (const id of scope.errors.keys()) {
      if (ids.has(id)) continue;
      scope.errors.delete(id);
      errorsRemoved = true;
    }
    if (errorsRemoved) publishHistoryErrors(scope);
    let changed = false;
    for (const id of Object.keys(scope.displayed)) {
      if (ids.has(id)) continue;
      delete scope.displayed[id];
      scope.cursors.delete(id);
      scope.streams.get(id)?.close();
      scope.streams.delete(id);
      scope.statuses.delete(id);
      changed = true;
    }
    for (const process of processes) {
      const previousStatus = scope.statuses.get(process.id);
      scope.statuses.set(process.id, process.status);
      if (isRunning(process) && !scope.streams.has(process.id)) {
        scope.displayed[process.id] ??= {
          executionProcess: process,
          entries: [],
        };
        const kind =
          process.executor_action.typ.type === 'ScriptRequest'
            ? 'raw'
            : 'normalized';
        const stream = streamJsonPatchEntries<PatchType>(
          `/api/execution-processes/${process.id}/${kind}-logs/ws`,
          {
            onEntries: (entries) => {
              if (
                scope.abort.signal.aborted ||
                !processesRef.current.some((p) => p.id === process.id)
              )
                return;
              const existing = scope.displayed[process.id]?.entries ?? [];
              // Do not blank an already visible live transcript during reconnect.
              if (entries.length < existing.length) return;
              scope.displayed[process.id] = {
                executionProcess: process,
                entries: entries.map((entry, index) => ({
                  ...entry,
                  patchKey: `${process.id}:${index}`,
                  executionProcessId: process.id,
                })),
              };
              emit(scope, 'running');
            },
            onFinished: () => {
              stream.close();
              // Leave the finished controller registered until status changes, so
              // an unrelated render cannot open a second replay of this stream.
              emit(scope, 'running');
            },
            onError: (error) =>
              console.warn('Unable to stream conversation', error),
          }
        );
        scope.streams.set(process.id, stream);
      }
      if (
        !isRunning(process) &&
        (previousStatus === ExecutionProcessStatus.running ||
          (scope.initialIds !== null &&
            !scope.initialIds.has(process.id) &&
            previousStatus === undefined))
      ) {
        // Let the finite live stream drain; refresh the final tail as well in
        // case the status event arrived before the last websocket patch.
        scope.cursors.delete(process.id);
        void fetchPage(scope, process, MIN_INITIAL_ENTRIES)
          .then(() => {
            if (scope.abort.signal.aborted) return;
            setIsLoadingHistory(scope.pending.size > 0);
            emit(scope, 'running');
          })
          .catch((error) => {
            if (
              !scope.abort.signal.aborted &&
              !(error instanceof CapturePending)
            ) {
              console.warn('Unable to refresh completed conversation', error);
              recordHistoryError(scope, process.id);
            }
          });
      }
    }
    if (changed) emit(scope, 'historic');
    if (
      !scope.initialLoaded &&
      !scope.loading &&
      !historyError &&
      scope.pending.size === 0
    ) {
      if (processes.length === 0) {
        if (!scope.emptyEmitted) {
          scope.emptyEmitted = true;
          emit(scope, 'initial');
        }
        return;
      }
      scope.emptyEmitted = false;
      void loadBatch(scope, true);
    }
  }, [
    scopeKey,
    processes,
    isLoading,
    isConnected,
    emit,
    fetchPage,
    loadBatch,
    publishHistoryErrors,
    recordHistoryError,
    revision,
    historyError,
    historyErrorDetail,
  ]);

  const loadMoreHistory = useCallback(async () => {
    if (isLoading || !isConnected) return;
    const scope = scopeRef.current;
    await loadBatch(scope, !scope.initialLoaded);
  }, [isLoading, isConnected, loadBatch]);

  const isFirstTurn = useMemo(
    () =>
      processes.filter(
        (p) =>
          p.executor_action.typ.type === 'CodingAgentInitialRequest' ||
          p.executor_action.typ.type === 'CodingAgentFollowUpRequest'
      ).length <= 1,
    [processes]
  );

  return {
    isFirstTurn,
    isLoadingHistory,
    hasMoreHistory,
    historyError,
    historyErrorDetail,
    loadMoreHistory,
  };
};

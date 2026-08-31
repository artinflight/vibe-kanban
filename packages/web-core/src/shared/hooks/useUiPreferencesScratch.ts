import { useCallback, useEffect, useRef } from 'react';
import { useScratch } from '@/shared/hooks/useScratch';
import { useDebouncedCallback } from '@/shared/hooks/useDebouncedCallback';
import {
  ScratchType,
  type UiPreferencesData,
  type ScratchPayload,
  type WorkspacePanelStateData,
  type ProjectCustomizationData,
  type JsonValue,
} from 'shared/types';
import {
  useUiPreferencesStore,
  DEFAULT_CREATE_DRAFT_WORKSPACE_BY_DEFAULT,
  DEFAULT_SHOW_LEFT_COLUMN_LINKS,
  type RightMainPanelMode,
  type ContextBarPosition,
  type SavedChatMessage,
  type WorkspacePanelState,
  type WorkspaceFilterState,
  type WorkspaceSortState,
  type WorkspacePrFilter,
  type WorkspaceSortBy,
  type WorkspaceSortOrder,
  type KanbanProjectViewSelection,
  type KanbanProjectViewPreferences,
  type ProjectCustomization,
} from '@/shared/stores/useUiPreferencesStore';
import type { RepoAction } from '@vibe/ui/components/RepoCard';
import { useAppRuntime } from '@/shared/hooks/useAppRuntime';
import { savedChatMessagesApi } from '@/shared/lib/api';
import {
  ApiError,
  durableUiPreferencesApi,
  type DurableUiPreferencesRecord,
  type WorkspaceCardColorRecord,
} from '@/shared/lib/api';

type UiPreferencesScratchData = UiPreferencesData & {
  local_project_order?: string[];
  show_left_column_links?: boolean | null;
  saved_chat_messages?: SavedChatMessage[];
};

// Stable UUID for global UI preferences (not tied to a workspace/user)
// This is a deterministic UUID v5 generated from the namespace "ui-preferences"
// Using a fixed UUID ensures all users/sessions share the same preferences record
const UI_PREFERENCES_ID = '00000000-0000-0000-0000-000000000001';
const SAVED_CHAT_MESSAGES_FALLBACK_URL = '/vk-saved-chat-messages.json';
const WORKSPACE_COLORS_FALLBACK_STORAGE_KEY = 'vk-workspace-colors';

function loadWorkspaceColorsFallback(): Record<string, string> {
  try {
    return normalizeWorkspaceColors(
      JSON.parse(
        window.localStorage.getItem(WORKSPACE_COLORS_FALLBACK_STORAGE_KEY) ??
          '{}'
      )
    );
  } catch {
    return {};
  }
}

function saveWorkspaceColorsFallback(colors: Record<string, string>): void {
  try {
    window.localStorage.setItem(
      WORKSPACE_COLORS_FALLBACK_STORAGE_KEY,
      JSON.stringify(colors)
    );
  } catch (error) {
    console.error('Failed to save workspace colors locally:', error);
  }
}

function normalizeWorkspaceColors(
  colors: UiPreferencesScratchData['workspace_colors']
): Record<string, string> {
  if (!colors) return {};

  return Object.fromEntries(
    Object.entries(colors).filter(
      (entry): entry is [string, string] => typeof entry[1] === 'string'
    )
  );
}

async function loadSavedChatMessagesFallback(): Promise<SavedChatMessage[]> {
  try {
    const response = await fetch(SAVED_CHAT_MESSAGES_FALLBACK_URL, {
      cache: 'no-store',
    });
    if (!response.ok) return [];

    const messages = await response.json();
    if (!Array.isArray(messages)) return [];

    return messages
      .filter(
        (message): message is SavedChatMessage =>
          typeof message?.id === 'string' &&
          typeof message.title === 'string' &&
          typeof message.content === 'string'
      )
      .map((message) => ({
        id: message.id,
        title: message.title.trim(),
        content: message.content,
      }))
      .filter((message) => message.title && message.content.trim());
  } catch {
    return [];
  }
}

/**
 * Converts store state to scratch data format (camelCase to snake_case)
 */
function storeToScratchData(state: {
  repoActions: Record<string, RepoAction>;
  expanded: Record<string, boolean>;
  contextBarPosition: ContextBarPosition;
  paneSizes: Record<string, number | string>;
  collapsedPaths: Record<string, string[]>;
  fileSearchRepoId: string | null;
  isLeftSidebarVisible: boolean;
  isRightSidebarVisible: boolean;
  isTerminalVisible: boolean;
  workspacePanelStates: Record<string, WorkspacePanelState>;
  workspaceFilters: WorkspaceFilterState;
  workspaceSort: WorkspaceSortState;
  selectedOrgId: string | null;
  selectedProjectId: string | null;
  localProjectOrder: string[];
  localProjectCustomizations: Record<string, ProjectCustomization>;
  workspaceColors: Record<string, string>;
  createDraftWorkspaceByDefault: boolean;
  showLeftColumnLinks: boolean;
  savedChatMessages: SavedChatMessage[];
  kanbanProjectViewSelections: Record<string, KanbanProjectViewSelection>;
  kanbanProjectViewPreferences: Record<
    string,
    Record<string, KanbanProjectViewPreferences>
  >;
}): UiPreferencesScratchData {
  const workspacePanelStates: { [key: string]: WorkspacePanelStateData } = {};
  for (const [key, value] of Object.entries(state.workspacePanelStates)) {
    workspacePanelStates[key] = {
      right_main_panel_mode: value.rightMainPanelMode,
      is_left_main_panel_visible: value.isLeftMainPanelVisible,
    };
  }
  const localProjectCustomizations: Record<string, ProjectCustomizationData> =
    {};
  for (const [key, value] of Object.entries(state.localProjectCustomizations)) {
    localProjectCustomizations[key] = {
      abbreviation: value.abbreviation ?? null,
      color: value.color ?? null,
    };
  }

  return {
    repo_actions: state.repoActions as { [key: string]: string },
    expanded: state.expanded,
    context_bar_position: state.contextBarPosition,
    pane_sizes: state.paneSizes as { [key: string]: JsonValue },
    collapsed_paths: state.collapsedPaths,
    file_search_repo_id: state.fileSearchRepoId,
    is_left_sidebar_visible: state.isLeftSidebarVisible,
    is_right_sidebar_visible: state.isRightSidebarVisible,
    is_terminal_visible: state.isTerminalVisible,
    workspace_panel_states: workspacePanelStates,
    workspace_filters: {
      project_ids: state.workspaceFilters.projectIds,
      pr_filter: state.workspaceFilters.prFilter,
    },
    workspace_sort: {
      sort_by: state.workspaceSort.sortBy,
      sort_order: state.workspaceSort.sortOrder,
    },
    selected_org_id: state.selectedOrgId,
    selected_project_id: state.selectedProjectId,
    local_project_order: state.localProjectOrder,
    local_project_customizations: localProjectCustomizations,
    workspace_colors: state.workspaceColors,
    create_draft_workspace_by_default: state.createDraftWorkspaceByDefault,
    show_left_column_links: state.showLeftColumnLinks,
    saved_chat_messages: state.savedChatMessages,
    kanban_project_view_selections: state.kanbanProjectViewSelections as Record<
      string,
      JsonValue
    >,
    kanban_project_view_preferences:
      state.kanbanProjectViewPreferences as Record<string, JsonValue>,
  };
}

/**
 * Converts scratch data to store state format (snake_case to camelCase)
 */
function scratchDataToStore(data: UiPreferencesScratchData): {
  repoActions: Record<string, RepoAction>;
  expanded: Record<string, boolean>;
  contextBarPosition: ContextBarPosition;
  paneSizes: Record<string, number | string>;
  collapsedPaths: Record<string, string[]>;
  fileSearchRepoId: string | null;
  isLeftSidebarVisible: boolean;
  isRightSidebarVisible: boolean;
  isTerminalVisible: boolean;
  workspacePanelStates: Record<string, WorkspacePanelState>;
  workspaceFilters: WorkspaceFilterState;
  workspaceSort: WorkspaceSortState;
  selectedOrgId: string | null;
  selectedProjectId: string | null;
  localProjectOrder: string[];
  localProjectCustomizations: Record<string, ProjectCustomization>;
  workspaceColors: Record<string, string>;
  createDraftWorkspaceByDefault: boolean;
  showLeftColumnLinks: boolean;
  savedChatMessages: SavedChatMessage[];
  kanbanProjectViewSelections: Record<string, KanbanProjectViewSelection>;
  kanbanProjectViewPreferences: Record<
    string,
    Record<string, KanbanProjectViewPreferences>
  >;
} {
  const workspacePanelStates: Record<string, WorkspacePanelState> = {};
  if (data.workspace_panel_states) {
    for (const [key, value] of Object.entries(data.workspace_panel_states)) {
      if (value) {
        workspacePanelStates[key] = {
          rightMainPanelMode:
            (value.right_main_panel_mode as RightMainPanelMode) ?? null,
          isLeftMainPanelVisible: value.is_left_main_panel_visible ?? true,
        };
      }
    }
  }

  // Backwards compatibility with older payloads that used
  // file_search_repo_by_project (project_id -> repo_id).
  const legacyFileSearchRepoByProject = (
    data as UiPreferencesData & {
      file_search_repo_by_project?: Record<string, string>;
    }
  ).file_search_repo_by_project;
  const legacyFileSearchRepoId =
    legacyFileSearchRepoByProject &&
    Object.values(legacyFileSearchRepoByProject)[0]
      ? Object.values(legacyFileSearchRepoByProject)[0]
      : null;

  return {
    repoActions: (data.repo_actions ?? {}) as Record<string, RepoAction>,
    expanded: (data.expanded ?? {}) as Record<string, boolean>,
    contextBarPosition:
      (data.context_bar_position as ContextBarPosition) ?? 'middle-right',
    paneSizes: (data.pane_sizes ?? {}) as Record<string, number | string>,
    collapsedPaths: (data.collapsed_paths ?? {}) as Record<string, string[]>,
    fileSearchRepoId: data.file_search_repo_id ?? legacyFileSearchRepoId,
    isLeftSidebarVisible: data.is_left_sidebar_visible ?? true,
    isRightSidebarVisible: data.is_right_sidebar_visible ?? true,
    isTerminalVisible: data.is_terminal_visible ?? true,
    workspacePanelStates,
    workspaceFilters: {
      projectIds: data.workspace_filters?.project_ids ?? [],
      prFilter:
        (data.workspace_filters?.pr_filter as WorkspacePrFilter) ?? 'all',
    },
    workspaceSort: {
      sortBy: (data.workspace_sort?.sort_by as WorkspaceSortBy) ?? 'updated_at',
      sortOrder:
        (data.workspace_sort?.sort_order as WorkspaceSortOrder) ?? 'desc',
    },
    selectedOrgId: data.selected_org_id ?? null,
    selectedProjectId: data.selected_project_id ?? null,
    localProjectOrder: data.local_project_order ?? [],
    localProjectCustomizations: (data.local_project_customizations ??
      {}) as Record<string, ProjectCustomization>,
    workspaceColors: normalizeWorkspaceColors(data.workspace_colors),
    createDraftWorkspaceByDefault:
      data.create_draft_workspace_by_default ??
      DEFAULT_CREATE_DRAFT_WORKSPACE_BY_DEFAULT,
    showLeftColumnLinks:
      data.show_left_column_links ?? DEFAULT_SHOW_LEFT_COLUMN_LINKS,
    savedChatMessages: Array.isArray(data.saved_chat_messages)
      ? data.saved_chat_messages
          .filter(
            (message): message is SavedChatMessage =>
              typeof message?.id === 'string' &&
              typeof message.title === 'string' &&
              typeof message.content === 'string'
          )
          .map((message) => ({
            id: message.id,
            title: message.title.trim(),
            content: message.content,
          }))
          .filter((message) => message.title && message.content.trim())
      : [],
    kanbanProjectViewSelections: (data.kanban_project_view_selections ??
      {}) as Record<string, KanbanProjectViewSelection>,
    kanbanProjectViewPreferences: (data.kanban_project_view_preferences ??
      {}) as Record<string, Record<string, KanbanProjectViewPreferences>>,
  };
}

/**
 * Hook that syncs UI preferences between Zustand store and server scratch storage.
 * Should be used once at the app root level.
 */
export function useUiPreferencesScratch() {
  const runtime = useAppRuntime();
  const { scratch, updateScratch, isLoading, isConnected } = useScratch(
    ScratchType.UI_PREFERENCES,
    UI_PREFERENCES_ID
  );

  // Track whether we've initialized from server
  const hasInitializedRef = useRef(false);
  // Track whether we're currently applying server data to prevent save loops
  const isApplyingServerDataRef = useRef(false);
  // Older local backends do not expose the durable saved-message routes. Keep
  // messages in scratch storage until a successful API read proves support.
  const hasDurableSavedChatMessagesRef = useRef(false);
  const hasHydratedSavedChatMessagesRef = useRef(false);
  const hasDurableUiPreferencesRef = useRef(false);
  const durableUiPreferencesRef = useRef<DurableUiPreferencesRecord | null>(
    null
  );
  const durableWriteChainRef = useRef(Promise.resolve());
  const lastSavedPayloadRef = useRef<string | null>(null);

  // Get current store state
  const storeState = useUiPreferencesStore((state) => ({
    repoActions: state.repoActions,
    expanded: state.expanded,
    contextBarPosition: state.contextBarPosition,
    paneSizes: state.paneSizes,
    collapsedPaths: state.collapsedPaths,
    fileSearchRepoId: state.fileSearchRepoId,
    isLeftSidebarVisible: state.isLeftSidebarVisible,
    isRightSidebarVisible: state.isRightSidebarVisible,
    isTerminalVisible: state.isTerminalVisible,
    workspacePanelStates: state.workspacePanelStates,
    workspaceFilters: state.workspaceFilters,
    workspaceSort: state.workspaceSort,
    selectedOrgId: state.selectedOrgId,
    selectedProjectId: state.selectedProjectId,
    localProjectOrder: state.localProjectOrder,
    localProjectCustomizations: state.localProjectCustomizations,
    workspaceColors: state.workspaceColors,
    createDraftWorkspaceByDefault: state.createDraftWorkspaceByDefault,
    showLeftColumnLinks: state.showLeftColumnLinks,
    savedChatMessages: state.savedChatMessages,
    kanbanProjectViewSelections: state.kanbanProjectViewSelections,
    kanbanProjectViewPreferences: state.kanbanProjectViewPreferences,
  }));

  // Extract scratch data
  const payload = scratch?.payload as ScratchPayload | undefined;
  const scratchData: UiPreferencesScratchData | undefined =
    payload?.type === 'UI_PREFERENCES'
      ? (payload.data as UiPreferencesScratchData)
      : undefined;

  // Save to server function
  const saveToServer = useCallback(async () => {
    if (isApplyingServerDataRef.current || !hasInitializedRef.current) {
      return;
    }

    const currentState = useUiPreferencesStore.getState();
    const nextData = storeToScratchData({
      repoActions: currentState.repoActions,
      expanded: currentState.expanded,
      contextBarPosition: currentState.contextBarPosition,
      paneSizes: currentState.paneSizes,
      collapsedPaths: currentState.collapsedPaths,
      fileSearchRepoId: currentState.fileSearchRepoId,
      isLeftSidebarVisible: currentState.isLeftSidebarVisible,
      isRightSidebarVisible: currentState.isRightSidebarVisible,
      isTerminalVisible: currentState.isTerminalVisible,
      workspacePanelStates: currentState.workspacePanelStates,
      workspaceFilters: currentState.workspaceFilters,
      workspaceSort: currentState.workspaceSort,
      selectedOrgId: currentState.selectedOrgId,
      selectedProjectId: currentState.selectedProjectId,
      localProjectOrder: currentState.localProjectOrder,
      localProjectCustomizations: currentState.localProjectCustomizations,
      workspaceColors: currentState.workspaceColors,
      createDraftWorkspaceByDefault: currentState.createDraftWorkspaceByDefault,
      showLeftColumnLinks: currentState.showLeftColumnLinks,
      savedChatMessages: currentState.savedChatMessages,
      kanbanProjectViewSelections: currentState.kanbanProjectViewSelections,
      kanbanProjectViewPreferences: currentState.kanbanProjectViewPreferences,
    });
    const data: UiPreferencesScratchData = {
      ...(scratchData ?? {}),
      ...nextData,
    };
    if (runtime === 'local' && hasDurableSavedChatMessagesRef.current) {
      delete data.saved_chat_messages;
    }
    if (runtime === 'local' && hasDurableUiPreferencesRef.current) {
      delete (data as Partial<UiPreferencesScratchData>).local_project_order;
      delete data.workspace_colors;
    }

    const serialized = JSON.stringify(data);
    if (serialized === lastSavedPayloadRef.current) {
      return;
    }

    try {
      await updateScratch({
        payload: {
          type: 'UI_PREFERENCES',
          data,
        },
      });
      lastSavedPayloadRef.current = serialized;
    } catch (e) {
      console.error('[useUiPreferencesScratch] Failed to save:', e);
    }
  }, [runtime, scratchData, updateScratch]);

  const { debounced: debouncedSave } = useDebouncedCallback(saveToServer, 500);

  const loadLocalSavedChatMessages = useCallback(
    async (fallbackMessages: SavedChatMessage[]) => {
      try {
        let durableMessages = await savedChatMessagesApi.list();
        hasDurableSavedChatMessagesRef.current = true;
        if (durableMessages.length === 0 && fallbackMessages.length > 0) {
          durableMessages = await Promise.all(
            fallbackMessages.map((message, position) =>
              savedChatMessagesApi.upsert({ ...message, position })
            )
          );
        }
        return durableMessages.map(({ id, title, content }) => ({
          id,
          title,
          content,
        }));
      } catch (error) {
        console.error('Failed to load durable saved chat messages:', error);
        return fallbackMessages.length > 0
          ? fallbackMessages
          : loadSavedChatMessagesFallback();
      }
    },
    []
  );

  const loadDurableUiPreferences = useCallback(async () => {
    try {
      let preferences = await durableUiPreferencesApi.get();
      hasDurableUiPreferencesRef.current = true;
      const fallbackColors = loadWorkspaceColorsFallback();
      if (
        Object.keys(preferences.workspace_colors).length === 0 &&
        Object.keys(fallbackColors).length > 0
      ) {
        const workspaceColors = { ...preferences.workspace_colors };
        for (const [workspaceId, color] of Object.entries(fallbackColors)) {
          const saved = await durableUiPreferencesApi.updateWorkspaceColor(
            workspaceId,
            color,
            null
          );
          if (saved) workspaceColors[workspaceId] = saved;
        }
        preferences = { ...preferences, workspace_colors: workspaceColors };
      }
      durableUiPreferencesRef.current = preferences;
      return preferences;
    } catch (error) {
      console.error('Failed to load durable UI preferences:', error);
      return null;
    }
  }, []);

  const applyDurableUiPreferences = useCallback(
    (preferences: DurableUiPreferencesRecord) => {
      durableUiPreferencesRef.current = preferences;
      isApplyingServerDataRef.current = true;
      useUiPreferencesStore.setState({
        localProjectOrder: preferences.project_order.project_ids,
        workspaceColors: Object.fromEntries(
          Object.entries(preferences.workspace_colors).map(
            ([workspaceId, record]) => [workspaceId, record.color]
          )
        ),
      });
      setTimeout(() => {
        isApplyingServerDataRef.current = false;
      }, 100);
    },
    []
  );

  const persistDurableUiPreferences = useCallback(
    async (projectIds: string[], workspaceColors: Record<string, string>) => {
      let durable = durableUiPreferencesRef.current;
      if (!durable) return;

      try {
        if (
          JSON.stringify(projectIds) !==
          JSON.stringify(durable.project_order.project_ids)
        ) {
          const projectOrder = await durableUiPreferencesApi.updateProjectOrder(
            projectIds,
            durable.project_order.revision
          );
          durable = { ...durable, project_order: projectOrder };
          durableUiPreferencesRef.current = durable;
        }

        const workspaceIds = new Set([
          ...Object.keys(durable.workspace_colors),
          ...Object.keys(workspaceColors),
        ]);
        for (const workspaceId of workspaceIds) {
          const existing = durable.workspace_colors[workspaceId];
          const color = workspaceColors[workspaceId] ?? null;
          if ((existing?.color ?? null) === color) continue;

          const updated = await durableUiPreferencesApi.updateWorkspaceColor(
            workspaceId,
            color,
            existing?.revision ?? null
          );
          const nextColors: Record<string, WorkspaceCardColorRecord> = {
            ...durable.workspace_colors,
          };
          if (updated) {
            nextColors[workspaceId] = updated;
          } else {
            delete nextColors[workspaceId];
          }
          durable = { ...durable, workspace_colors: nextColors };
          durableUiPreferencesRef.current = durable;
        }
      } catch (error) {
        if (error instanceof ApiError && error.statusCode === 409) {
          const canonical = await loadDurableUiPreferences();
          if (canonical) applyDurableUiPreferences(canonical);
          return;
        }
        console.error('Failed to save durable UI preferences:', error);
      }
    },
    [applyDurableUiPreferences, loadDurableUiPreferences]
  );

  // Saved messages must remain available even when the UI-preferences scratch
  // stream is missing or delayed. This also supports frontend-only deploys
  // against an older backend by loading the immutable sidecar fallback.
  useEffect(() => {
    if (runtime !== 'local' || hasHydratedSavedChatMessagesRef.current) return;

    hasHydratedSavedChatMessagesRef.current = true;
    void loadLocalSavedChatMessages([]).then((savedChatMessages) => {
      if (savedChatMessages.length > 0) {
        useUiPreferencesStore.setState({ savedChatMessages });
      }
    });
  }, [loadLocalSavedChatMessages, runtime]);

  // Initialize store from server data when first loaded
  useEffect(() => {
    if (hasInitializedRef.current || isLoading || !isConnected) {
      return;
    }

    if (scratchData) {
      hasInitializedRef.current = true;
      isApplyingServerDataRef.current = true;
      lastSavedPayloadRef.current = JSON.stringify(scratchData);

      void (async () => {
        const serverState = scratchDataToStore(scratchData);
        const durablePreferences =
          runtime === 'local' ? await loadDurableUiPreferences() : null;
        const workspaceColors = durablePreferences
          ? Object.fromEntries(
              Object.entries(durablePreferences.workspace_colors).map(
                ([workspaceId, record]) => [workspaceId, record.color]
              )
            )
          : {
              ...loadWorkspaceColorsFallback(),
              ...serverState.workspaceColors,
            };
        const fallbackMessages =
          serverState.savedChatMessages.length > 0
            ? serverState.savedChatMessages
            : await loadSavedChatMessagesFallback();
        const savedChatMessages =
          runtime === 'local'
            ? await loadLocalSavedChatMessages(fallbackMessages)
            : fallbackMessages;

        useUiPreferencesStore.setState({
          repoActions: serverState.repoActions,
          expanded: serverState.expanded,
          contextBarPosition: serverState.contextBarPosition,
          paneSizes: serverState.paneSizes,
          collapsedPaths: serverState.collapsedPaths,
          fileSearchRepoId: serverState.fileSearchRepoId,
          isLeftSidebarVisible: serverState.isLeftSidebarVisible,
          isRightSidebarVisible: serverState.isRightSidebarVisible,
          isTerminalVisible: serverState.isTerminalVisible,
          workspacePanelStates: serverState.workspacePanelStates,
          workspaceFilters: serverState.workspaceFilters,
          workspaceSort: serverState.workspaceSort,
          selectedOrgId: serverState.selectedOrgId,
          selectedProjectId: serverState.selectedProjectId,
          localProjectOrder:
            durablePreferences?.project_order.project_ids ??
            serverState.localProjectOrder,
          localProjectCustomizations: serverState.localProjectCustomizations,
          workspaceColors,
          createDraftWorkspaceByDefault:
            serverState.createDraftWorkspaceByDefault,
          showLeftColumnLinks: serverState.showLeftColumnLinks,
          savedChatMessages,
          kanbanProjectViewSelections: serverState.kanbanProjectViewSelections,
          kanbanProjectViewPreferences:
            serverState.kanbanProjectViewPreferences,
        });
        saveWorkspaceColorsFallback(workspaceColors);

        setTimeout(() => {
          isApplyingServerDataRef.current = false;
        }, 100);
      })();
    }
  }, [
    isLoading,
    isConnected,
    loadLocalSavedChatMessages,
    loadDurableUiPreferences,
    runtime,
    scratchData,
  ]);

  // Subscribe to store changes and save to server
  useEffect(() => {
    const unsubscribe = useUiPreferencesStore.subscribe(() => {
      if (!isApplyingServerDataRef.current && hasInitializedRef.current) {
        const state = useUiPreferencesStore.getState();
        saveWorkspaceColorsFallback(state.workspaceColors);
        if (hasDurableUiPreferencesRef.current) {
          durableWriteChainRef.current = durableWriteChainRef.current.then(() =>
            persistDurableUiPreferences(
              state.localProjectOrder,
              state.workspaceColors
            )
          );
        }
        debouncedSave();
      }
    });

    return unsubscribe;
  }, [debouncedSave, persistDurableUiPreferences]);

  return {
    isLoading,
    isConnected,
    // Expose for debugging
    scratchData,
    storeState,
  };
}

import { scratchApi, ApiError } from '@/shared/lib/api';
import {
  ScratchType,
  type DraftWorkspaceRepo,
  type ProjectStatusConfigData,
  type ScratchPayload,
} from 'shared/types';

const SCRATCH_TYPE = ScratchType.PROJECT_REPO_DEFAULTS;

export interface ProjectLocalDefaults {
  repos: DraftWorkspaceRepo[];
  statuses: ProjectStatusConfigData[];
}

export function getDefaultProjectStatusDefaults(): ProjectStatusConfigData[] {
  return [
    {
      id: 'todo',
      name: 'To do',
      color: '220 70% 52%',
      hidden: false,
      sort_order: 0,
    },
    {
      id: 'in_progress',
      name: 'In progress',
      color: '42 90% 55%',
      hidden: false,
      sort_order: 1,
    },
    {
      id: 'status_onhold',
      name: 'On Hold',
      color: '220 70% 52%',
      hidden: false,
      sort_order: 2,
    },
    {
      id: 'status_longrunning',
      name: 'Long Running',
      color: '220 70% 52%',
      hidden: false,
      sort_order: 3,
    },
    {
      id: 'in_review',
      name: 'In review',
      color: '280 55% 58%',
      hidden: false,
      sort_order: 4,
    },
    {
      id: 'cancelled',
      name: 'Cancelled',
      color: '0 0% 55%',
      hidden: true,
      sort_order: 5,
    },
    {
      id: 'status_tomerge',
      name: 'To merge',
      color: '220 70% 52%',
      hidden: false,
      sort_order: 6,
    },
    {
      id: 'in_staging',
      name: 'In Staging',
      color: '196 72% 47%',
      hidden: false,
      sort_order: 7,
    },
    {
      id: 'status_hotfixpath',
      name: 'Hotfix Path',
      color: '220 70% 52%',
      hidden: false,
      sort_order: 8,
    },
    {
      id: 'done',
      name: 'Done',
      color: '145 55% 42%',
      hidden: false,
      sort_order: 9,
    },
  ];
}

async function getProjectLocalDefaults(
  projectId: string
): Promise<ProjectLocalDefaults | null> {
  try {
    const scratch = await scratchApi.get(SCRATCH_TYPE, projectId);
    const payload = scratch.payload as ScratchPayload;
    if (payload?.type === 'PROJECT_REPO_DEFAULTS') {
      return {
        repos: payload.data.repos ?? [],
        statuses: payload.data.statuses ?? [],
      };
    }
    return null;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    console.error('[useProjectRepoDefaults] Failed to read defaults:', error);
    return null;
  }
}

async function saveProjectLocalDefaults(
  projectId: string,
  data: ProjectLocalDefaults
): Promise<void> {
  await scratchApi.update(SCRATCH_TYPE, projectId, {
    payload: {
      type: 'PROJECT_REPO_DEFAULTS',
      data: {
        repos: data.repos,
        statuses: data.statuses,
      },
    },
  });
}

/**
 * Read project repo defaults from scratch storage.
 * Returns null if no defaults have been saved for this project.
 */
export async function getProjectRepoDefaults(
  projectId: string
): Promise<DraftWorkspaceRepo[] | null> {
  const defaults = await getProjectLocalDefaults(projectId);
  return defaults?.repos ?? null;
}

/**
 * Save project repo defaults to scratch storage (upsert).
 */
export async function saveProjectRepoDefaults(
  projectId: string,
  repos: DraftWorkspaceRepo[]
): Promise<void> {
  const current = (await getProjectLocalDefaults(projectId)) ?? {
    repos: [],
    statuses: getDefaultProjectStatusDefaults(),
  };
  await saveProjectLocalDefaults(projectId, {
    ...current,
    repos,
    statuses:
      current.statuses.length > 0
        ? current.statuses
        : getDefaultProjectStatusDefaults(),
  });
}

export async function getProjectStatusDefaults(
  projectId: string
): Promise<ProjectStatusConfigData[] | null> {
  const defaults = await getProjectLocalDefaults(projectId);
  return defaults?.statuses ?? null;
}

export async function saveProjectStatusDefaults(
  projectId: string,
  statuses: ProjectStatusConfigData[]
): Promise<void> {
  const current = (await getProjectLocalDefaults(projectId)) ?? {
    repos: [],
    statuses: [],
  };
  await saveProjectLocalDefaults(projectId, {
    ...current,
    statuses,
  });
}

/**
 * Read project repo defaults and filter out repos that no longer exist.
 * Returns an empty array if no defaults are saved or all saved repos are stale.
 */
export async function getValidProjectRepoDefaults(
  projectId: string,
  availableRepoIds: Set<string>
): Promise<DraftWorkspaceRepo[]> {
  const defaults = await getProjectRepoDefaults(projectId);
  if (!defaults) {
    return [];
  }
  return defaults.filter((repo) => availableRepoIds.has(repo.repo_id));
}

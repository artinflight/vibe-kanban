import type { DisplayEntry } from '@/shared/hooks/useConversationHistory/types';
import type { NormalizedEntry } from 'shared/types';

type SubagentState = 'running' | 'unresolved' | 'completed' | 'not_found';
type ToolEntry = Extract<
  NormalizedEntry['entry_type'],
  { type: 'tool_use' }
> & {
  action_type: Extract<
    Extract<NormalizedEntry['entry_type'], { type: 'tool_use' }>['action_type'],
    { action: 'tool' }
  >;
};

export interface SubagentActivityItem {
  id: string;
  label: string;
  state: SubagentState;
}

export interface SubagentActivity {
  activeCount: number;
  unresolvedCount: number;
  completedCount: number;
  notFoundCount: number;
  items: SubagentActivityItem[];
  shouldConfirmBeforeSend: boolean;
}

function parseJsonValue(value: unknown): unknown {
  if (typeof value !== 'string') {
    return value;
  }

  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

function getResultPayload(result: unknown): unknown {
  if (!result || typeof result !== 'object') {
    return null;
  }

  const value = (result as { value?: unknown }).value;
  return parseJsonValue(value);
}

function getString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function getAgentLabel(agentId: string, nickname: unknown): string {
  const name = getString(nickname);
  return name ? `${name} (${agentId.slice(0, 8)})` : agentId.slice(0, 8);
}

function setAgentState(
  agents: Map<string, SubagentActivityItem>,
  agentId: string,
  state: SubagentState,
  nickname?: unknown
) {
  const existing = agents.get(agentId);
  const label = existing?.label ?? getAgentLabel(agentId, nickname);
  agents.set(agentId, { id: agentId, label, state });
}

function getToolEntries(entries: DisplayEntry[]): ToolEntry[] {
  return entries.flatMap((entry) => {
    if (entry.type !== 'NORMALIZED_ENTRY') {
      return [];
    }

    const entryType = entry.content.entry_type;
    if (
      entryType.type !== 'tool_use' ||
      entryType.action_type.action !== 'tool'
    ) {
      return [];
    }

    return [entryType as ToolEntry];
  });
}

function isSpawnAgentTool(toolName: string): boolean {
  return toolName === 'spawn_agent' || toolName.endsWith('.spawn_agent');
}

function isWaitAgentTool(toolName: string): boolean {
  return toolName === 'wait_agent' || toolName.endsWith('.wait_agent');
}

export function deriveSubagentActivity(
  entries: DisplayEntry[]
): SubagentActivity {
  const agents = new Map<string, SubagentActivityItem>();

  for (const entryType of getToolEntries(entries)) {
    const toolName = entryType.tool_name;
    const action = entryType.action_type;
    const args = action.arguments;
    const resultPayload = getResultPayload(action.result);

    if (isSpawnAgentTool(toolName)) {
      const agentId = getString(
        resultPayload && typeof resultPayload === 'object'
          ? (resultPayload as { agent_id?: unknown }).agent_id
          : null
      );
      if (agentId) {
        setAgentState(
          agents,
          agentId,
          entryType.status.status === 'failed' ? 'not_found' : 'unresolved',
          resultPayload && typeof resultPayload === 'object'
            ? (resultPayload as { nickname?: unknown }).nickname
            : null
        );
      }
      continue;
    }

    if (isWaitAgentTool(toolName)) {
      const targets = Array.isArray(
        args && typeof args === 'object'
          ? (args as { targets?: unknown }).targets
          : null
      )
        ? ((args as { targets: unknown[] }).targets
            .map(getString)
            .filter(Boolean) as string[])
        : [];

      if (entryType.status.status === 'created') {
        for (const agentId of targets) {
          setAgentState(agents, agentId, 'running');
        }
        continue;
      }

      if (!resultPayload || typeof resultPayload !== 'object') {
        continue;
      }

      const statusMap = (resultPayload as { status?: unknown }).status;
      const timedOut = Boolean(
        (resultPayload as { timed_out?: unknown }).timed_out
      );

      if (statusMap && typeof statusMap === 'object') {
        for (const [agentId, status] of Object.entries(statusMap)) {
          if (status === 'not_found') {
            const existing = agents.get(agentId);
            setAgentState(
              agents,
              agentId,
              existing &&
                (existing.state === 'running' ||
                  existing.state === 'unresolved')
                ? existing.state
                : 'not_found'
            );
          } else if (
            status &&
            typeof status === 'object' &&
            'completed' in status
          ) {
            setAgentState(agents, agentId, 'completed');
          } else if (timedOut) {
            setAgentState(agents, agentId, 'running');
          } else {
            setAgentState(agents, agentId, 'unresolved');
          }
        }
      } else if (timedOut) {
        for (const agentId of targets) {
          setAgentState(agents, agentId, 'running');
        }
      }
    }
  }

  const items = Array.from(agents.values());
  const activeCount = items.filter((item) => item.state === 'running').length;
  const unresolvedCount = items.filter(
    (item) => item.state === 'unresolved'
  ).length;
  const completedCount = items.filter(
    (item) => item.state === 'completed'
  ).length;
  const notFoundCount = items.filter(
    (item) => item.state === 'not_found'
  ).length;

  return {
    activeCount,
    unresolvedCount,
    completedCount,
    notFoundCount,
    items,
    shouldConfirmBeforeSend: activeCount + unresolvedCount + notFoundCount > 0,
  };
}

import type {
  BaseCodingAgent,
  ExecutorConfig,
  ModelInfo,
  ModelSelectorConfig,
  ReasoningOption,
} from 'shared/types';

export const DEFAULT_CODEX_MODEL_ID = 'gpt-6.2-sol';

// Compatibility with deployed backends whose static catalog predates GPT-6.2.
// Keep this list aligned with the reasoning IDs accepted by VK's Codex
// executor. Any additional options discovered from a newer backend are also
// retained by mergeReasoningOptions.
const reasoningOptions: ReasoningOption[] = [
  { id: 'low', label: 'Low', is_default: false },
  { id: 'medium', label: 'Medium', is_default: false },
  { id: 'high', label: 'High', is_default: true },
  { id: 'xhigh', label: 'Extra High', is_default: false },
  { id: 'max', label: 'Max', is_default: false },
];

const currentModels: ModelInfo[] = [
  {
    id: DEFAULT_CODEX_MODEL_ID,
    name: 'GPT-6.2 Sol',
    provider_id: null,
    reasoning_options: reasoningOptions,
  },
  {
    id: 'gpt-6.2-astra',
    name: 'GPT-6.2 Astra',
    provider_id: null,
    reasoning_options: reasoningOptions,
  },
];

function parseCodexModel(id: string) {
  const match = /^gpt-(\d+)(?:\.(\d+))?(?:-(.+))?$/i.exec(id);
  if (!match) return null;
  return {
    major: Number(match[1]),
    minor: Number(match[2] ?? 0),
    version: match[2] === undefined ? match[1] : `${match[1]}.${match[2]}`,
    family: match[3]?.toLowerCase() ?? '',
  };
}

function normalizeModelDisplay(models: ModelInfo[]): ModelInfo[] {
  const familyOrder = ['astra', 'sol', 'terra', 'luna'];
  return models
    .map((model) => {
      const parsed = parseCodexModel(model.id);
      if (!parsed) return model;
      const family = parsed.family
        .split(/[-_]/)
        .filter(Boolean)
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
      return {
        ...model,
        name: `GPT-${parsed.version}${family ? ` ${family}` : ''}`,
      };
    })
    .sort((first, second) => {
      const firstVersion = parseCodexModel(first.id);
      const secondVersion = parseCodexModel(second.id);
      if (firstVersion && secondVersion) {
        const versionOrder =
          secondVersion.major - firstVersion.major ||
          secondVersion.minor - firstVersion.minor;
        if (versionOrder) return versionOrder;
        const firstFamily = familyOrder.indexOf(firstVersion.family);
        const secondFamily = familyOrder.indexOf(secondVersion.family);
        const familyRank =
          (firstFamily < 0 ? familyOrder.length : firstFamily) -
          (secondFamily < 0 ? familyOrder.length : secondFamily);
        if (familyRank) return familyRank;
      } else if (firstVersion || secondVersion) {
        return firstVersion ? -1 : 1;
      }
      return first.name.localeCompare(second.name, undefined, {
        numeric: true,
        sensitivity: 'base',
      });
    });
}

function mergeReasoningOptions(
  required: ReasoningOption[],
  discovered: ReasoningOption[]
): ReasoningOption[] {
  const discoveredById = new Map(
    discovered.map((option) => [option.id.toLowerCase(), option])
  );
  const requiredIds = new Set(
    required.map((option) => option.id.toLowerCase())
  );
  return [
    ...required.map(
      (option) => discoveredById.get(option.id.toLowerCase()) ?? option
    ),
    ...discovered.filter((option) => !requiredIds.has(option.id.toLowerCase())),
  ];
}

export function normalizeCodexModelSelector(
  agent: BaseCodingAgent | null,
  config: ModelSelectorConfig | null
): ModelSelectorConfig | null {
  if (agent !== 'CODEX' || !config) return config;
  const models = config.models.filter((model) => {
    const version = /^gpt-(\d+)/i.exec(model.id);
    return !version || Number(version[1]) >= 6;
  });
  const discoveredById = new Map(
    models.map((model) => [model.id.toLowerCase(), model])
  );
  const currentIds = new Set(
    currentModels.map((model) => model.id.toLowerCase())
  );
  const requiredModels = currentModels.map((required) => {
    const discovered = discoveredById.get(required.id.toLowerCase());
    return discovered
      ? {
          ...discovered,
          name: required.name,
          reasoning_options: mergeReasoningOptions(
            required.reasoning_options,
            discovered.reasoning_options
          ),
        }
      : required;
  });

  return {
    ...config,
    default_model: DEFAULT_CODEX_MODEL_ID,
    models: normalizeModelDisplay([
      ...requiredModels,
      ...models.filter((model) => !currentIds.has(model.id.toLowerCase())),
    ]),
  };
}

export function applyFrontendCodexDefault(
  executor: BaseCodingAgent | null,
  variant: string | null,
  presetOptions: ExecutorConfig | null | undefined
): ExecutorConfig | null | undefined {
  if (executor !== 'CODEX' || (variant !== null && variant !== 'DEFAULT')) {
    return presetOptions;
  }

  return {
    ...(presetOptions ?? { executor }),
    model_id: DEFAULT_CODEX_MODEL_ID,
  };
}

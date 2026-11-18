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
    const version = /^gpt-(\d+)(?:\.(\d+))?(?:-|$)/i.exec(model.id);
    if (!version) return true;
    return (
      Number(version[1]) > 5 ||
      (Number(version[1]) === 5 && Number(version[2] ?? 0) >= 6)
    );
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
    models: [
      ...requiredModels,
      ...models.filter((model) => !currentIds.has(model.id.toLowerCase())),
    ],
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

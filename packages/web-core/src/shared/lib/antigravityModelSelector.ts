import type {
  BaseCodingAgent,
  ModelInfo,
  ModelSelectorConfig,
} from 'shared/types';

export const DEFAULT_ANTIGRAVITY_MODEL = 'gemini-3.8-flash-low';

export const ANTIGRAVITY_MODELS: ModelInfo[] = [
  {
    id: 'gemini-4-argon-medium',
    name: 'Gemini 4 Argon (Medium)',
    provider_id: null,
    reasoning_options: [],
  },
  {
    id: 'gemini-4-argon-high',
    name: 'Gemini 4 Argon (High)',
    provider_id: null,
    reasoning_options: [],
  },
  {
    id: 'gemini-4-argon-low',
    name: 'Gemini 4 Argon (Low)',
    provider_id: null,
    reasoning_options: [],
  },
  {
    id: 'gemini-3.8-flash-high',
    name: 'Gemini 3.8 Flash (High)',
    provider_id: null,
    reasoning_options: [],
  },
  {
    id: 'gemini-3.8-flash-medium',
    name: 'Gemini 3.8 Flash (Medium)',
    provider_id: null,
    reasoning_options: [],
  },
  {
    id: 'gemini-3.8-flash-low',
    name: 'Gemini 3.8 Flash (Low)',
    provider_id: null,
    reasoning_options: [],
  },
];

export function normalizeAntigravityModelSelector(
  agent: BaseCodingAgent | null,
  config: ModelSelectorConfig | null,
  presetModelId?: string | null,
  selectedModelId?: string | null
): ModelSelectorConfig | null {
  if (agent !== 'ANTIGRAVITY' || !config) return config;

  const builtinById = new Map(
    ANTIGRAVITY_MODELS.map((model) => [model.id.toLowerCase(), model])
  );
  const existingById = new Map<string, ModelInfo>();
  const customModels: ModelInfo[] = [];

  for (const model of config.models) {
    const key = model.id.toLowerCase();
    if (existingById.has(key)) continue;
    existingById.set(key, model);
    if (!builtinById.has(key)) {
      customModels.push(model);
    }
  }

  for (const candidate of [presetModelId, selectedModelId]) {
    const trimmed = candidate?.trim();
    if (!trimmed) continue;
    const key = trimmed.toLowerCase();
    if (builtinById.has(key) || existingById.has(key)) continue;
    const custom: ModelInfo = {
      id: trimmed,
      name: trimmed,
      provider_id: null,
      reasoning_options: [],
    };
    existingById.set(key, custom);
    customModels.push(custom);
  }

  const builtinModels = ANTIGRAVITY_MODELS.map((builtin) => {
    const existing = existingById.get(builtin.id.toLowerCase());
    if (!existing) return builtin;
    return {
      ...existing,
      name:
        existing.name &&
        existing.name.toLowerCase() !== existing.id.toLowerCase()
          ? existing.name
          : builtin.name,
    };
  });

  const normalizedPreset = presetModelId?.trim() || null;

  return {
    ...config,
    models: [...customModels, ...builtinModels],
    default_model:
      config.default_model ?? normalizedPreset ?? DEFAULT_ANTIGRAVITY_MODEL,
  };
}

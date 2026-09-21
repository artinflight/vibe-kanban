import type { BaseCodingAgent, ModelSelectorConfig } from 'shared/types';

// Compatibility with deployed backends whose static catalog predates GPT-6.
// These levels are supported by both native GPT-6 and VK's ReasoningEffort enum.
const reasoningOptions = ['low', 'medium', 'high', 'xhigh', 'max'].map(
  (id) => ({
    id,
    label: id === 'xhigh' ? 'Xhigh' : id[0].toUpperCase() + id.slice(1),
    is_default: id === 'xhigh',
  })
);

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
  const astra = models.find((model) => model.id === 'gpt-6-astra');
  if (astra) {
    return {
      ...config,
      models: models.map((model) =>
        model === astra && model.reasoning_options.length === 0
          ? { ...model, reasoning_options: reasoningOptions }
          : model
      ),
    };
  }
  return {
    ...config,
    models: [
      {
        id: 'gpt-6-astra',
        name: 'GPT-6 Astra',
        provider_id: null,
        reasoning_options: reasoningOptions,
      },
      ...models,
    ],
  };
}

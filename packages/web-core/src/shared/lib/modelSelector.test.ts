import { describe, expect, it } from 'vitest';
import type { ModelSelectorConfig } from 'shared/types';
import { appendPresetModel, filterCurrentCodexModels } from './modelSelector';

function configWithModels(ids: string[]): ModelSelectorConfig {
  return {
    models: ids.map((id) => ({
      id,
      name: id,
      provider_id: null,
      reasoning_options: [],
    })),
    providers: [],
    permissions: [],
  };
}

describe('Codex model menu', () => {
  it('uses the official display name for an injected Astra preset', () => {
    const result = appendPresetModel(configWithModels([]), 'gpt-6-astra');

    expect(result?.models).toEqual([
      expect.objectContaining({ id: 'gpt-6-astra', name: 'GPT-6 Astra' }),
    ]);
  });

  it('keeps GPT-6 Astra and GPT-5.6 models only', () => {
    const result = filterCurrentCodexModels(
      configWithModels([
        'gpt-6-astra',
        'gpt-5.6-sol',
        'gpt-5.6-terra',
        'gpt-5.6-luna',
        'gpt-5.5',
        'gpt-5.4-mini',
        'gpt-5.3-codex',
      ])
    );

    expect(result?.models.map((model) => model.id)).toEqual([
      'gpt-6-astra',
      'gpt-5.6-sol',
      'gpt-5.6-terra',
      'gpt-5.6-luna',
    ]);
  });
});

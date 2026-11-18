import assert from 'node:assert/strict';
import { test } from 'node:test';
import type {
  BaseCodingAgent,
  ExecutorConfig,
  ModelSelectorConfig,
} from 'shared/types';
import {
  DEFAULT_CODEX_MODEL_ID,
  applyFrontendCodexDefault,
  normalizeCodexModelSelector,
} from './codexModelSelector.ts';

const codex = 'CODEX' as BaseCodingAgent;
const claude = 'CLAUDE_CODE' as BaseCodingAgent;

function configWithModels(ids: string[]): ModelSelectorConfig {
  return {
    models: ids.map((id) => ({
      id,
      name: id,
      provider_id: null,
      reasoning_options: [],
    })),
    providers: [],
    default_model: null,
    default_provider: null,
    supports_routing: true,
  };
}

test('adds GPT-6.2 Sol and Astra with every Vibe Codex reasoning tier', () => {
  const result = normalizeCodexModelSelector(
    codex,
    configWithModels(['gpt-5.5', 'gpt-5.6-sol', 'gpt-6.1-terra'])
  )!;

  assert.equal(result.default_model, DEFAULT_CODEX_MODEL_ID);
  assert.deepEqual(
    result.models.slice(0, 2).map((model) => [model.id, model.name]),
    [
      ['gpt-6.2-sol', 'GPT-6.2 Sol'],
      ['gpt-6.2-astra', 'GPT-6.2 Astra'],
    ]
  );
  for (const model of result.models.slice(0, 2)) {
    assert.deepEqual(
      model.reasoning_options.map((option) => option.id),
      ['low', 'medium', 'high', 'xhigh', 'max']
    );
  }
  assert.deepEqual(
    result.models.slice(2).map((model) => model.id),
    ['gpt-5.6-sol', 'gpt-6.1-terra']
  );
});

test('preserves discovered metadata and additional backend reasoning tiers', () => {
  const config = configWithModels(['gpt-6.2-sol']);
  config.models[0].name = 'Backend label';
  config.models[0].reasoning_options = [
    { id: 'low', label: 'Fast responses', is_default: false },
    { id: 'ultra', label: 'Ultra', is_default: true },
  ];

  const result = normalizeCodexModelSelector(codex, config)!;

  assert.equal(result.models[0].name, 'GPT-6.2 Sol');
  assert.deepEqual(result.models[0].reasoning_options[0], {
    id: 'low',
    label: 'Fast responses',
    is_default: false,
  });
  assert.equal(result.models[0].reasoning_options.at(-1)?.id, 'ultra');
});

test('uses GPT-6.2 Sol only for the default Codex variant', () => {
  const preset: ExecutorConfig = {
    executor: codex,
    model_id: 'gpt-6.1-sol',
    reasoning_id: 'high',
  };

  assert.deepEqual(applyFrontendCodexDefault(codex, 'DEFAULT', preset), {
    ...preset,
    model_id: DEFAULT_CODEX_MODEL_ID,
  });
  assert.equal(applyFrontendCodexDefault(codex, 'REVIEW', preset), preset);
  assert.equal(applyFrontendCodexDefault(claude, 'DEFAULT', preset), preset);
});

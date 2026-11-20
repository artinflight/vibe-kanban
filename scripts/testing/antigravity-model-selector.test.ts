import assert from "node:assert/strict";
import test from "node:test";
import {
  ANTIGRAVITY_MODELS,
  DEFAULT_ANTIGRAVITY_MODEL,
  normalizeAntigravityModelSelector,
} from "../../packages/web-core/src/shared/lib/antigravityModelSelector";
import {
  appendPresetModel,
  getSelectedModel,
  resolveDefaultModelId,
} from "../../packages/web-core/src/shared/lib/modelSelector";
import type { ModelSelectorConfig } from "../../shared/types";

const emptyConfig = {
  models: [],
  providers: [],
  default_model: null,
  agents: [],
  permissions: ["SUPERVISED"],
} as unknown as ModelSelectorConfig;

test("populates Antigravity provider models and repairs raw preset placeholder", () => {
  const withPreset = appendPresetModel(emptyConfig, DEFAULT_ANTIGRAVITY_MODEL);
  const result = normalizeAntigravityModelSelector(
    "ANTIGRAVITY",
    withPreset,
    DEFAULT_ANTIGRAVITY_MODEL,
  )!;

  assert.deepEqual(
    result.models.map((m) => [m.id, m.name]),
    ANTIGRAVITY_MODELS.map((m) => [m.id, m.name]),
  );
  assert.equal(result.default_model, DEFAULT_ANTIGRAVITY_MODEL);
  assert.equal(
    result.models.filter((m) => m.id === DEFAULT_ANTIGRAVITY_MODEL).length,
    1,
  );

  const defaultId = resolveDefaultModelId(
    result.models,
    null,
    result.default_model,
    false,
  );
  assert.equal(defaultId, DEFAULT_ANTIGRAVITY_MODEL);
  assert.equal(
    getSelectedModel(result.models, null, defaultId)?.name,
    "Gemini 3.8 Flash (Low)",
  );
});

test("preserves existing default and saved profile or session selection", () => {
  const profileSaved = normalizeAntigravityModelSelector(
    "ANTIGRAVITY",
    appendPresetModel(emptyConfig, "gemini-4-argon-high"),
    "gemini-4-argon-high",
  )!;
  assert.equal(profileSaved.default_model, "gemini-4-argon-high");
  assert.equal(
    getSelectedModel(profileSaved.models, null, "gemini-4-argon-high")?.name,
    "Gemini 4 Argon (High)",
  );

  const sessionSaved = normalizeAntigravityModelSelector(
    "ANTIGRAVITY",
    appendPresetModel(emptyConfig, DEFAULT_ANTIGRAVITY_MODEL),
    DEFAULT_ANTIGRAVITY_MODEL,
    "gemini-4-argon-medium",
  )!;
  assert.equal(sessionSaved.default_model, DEFAULT_ANTIGRAVITY_MODEL);
  assert.equal(
    getSelectedModel(sessionSaved.models, null, "gemini-4-argon-medium")?.name,
    "Gemini 4 Argon (Medium)",
  );
});

test("preserves custom saved models and leaves other executors untouched", () => {
  const customSaved = normalizeAntigravityModelSelector(
    "ANTIGRAVITY",
    emptyConfig,
    DEFAULT_ANTIGRAVITY_MODEL,
    "gemini-custom-preview",
  )!;
  assert.equal(customSaved.models[0].id, "gemini-custom-preview");
  assert.equal(customSaved.models.length, ANTIGRAVITY_MODELS.length + 1);
  assert.equal(
    getSelectedModel(customSaved.models, null, "gemini-custom-preview")?.id,
    "gemini-custom-preview",
  );

  assert.equal(
    normalizeAntigravityModelSelector("CLAUDE_CODE", emptyConfig),
    emptyConfig,
  );
  assert.equal(normalizeAntigravityModelSelector("ANTIGRAVITY", null), null);
});

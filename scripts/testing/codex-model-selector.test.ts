import assert from "node:assert/strict";
import test from "node:test";
import { normalizeCodexModelSelector } from "../../packages/web-core/src/shared/lib/codexModelSelector";
import type { ModelSelectorConfig } from "../../shared/types";

const model = (id: string) => ({
  id,
  name: id,
  provider_id: null,
  reasoning_options: [],
});
const config = {
  models: [
    "gpt-5.1-codex-max",
    "gpt-5.5",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
  ].map(model),
  providers: [],
  default_model: "gpt-5.6-sol",
  permissions: [],
} as unknown as ModelSelectorConfig;
test("hides old Codex choices and restores GPT-6 reasoning", () => {
  const result = normalizeCodexModelSelector("CODEX", config)!;
  assert.deepEqual(
    result.models.map((m) => m.id),
    ["gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
  );
  assert.deepEqual(
    result.models[0].reasoning_options.map((o) => o.id),
    ["low", "medium", "high", "xhigh", "max"],
  );
  assert.equal(result.default_model, config.default_model);
  assert.equal(config.models.length, 5);
});
test("repairs custom GPT-6 placeholder without duplication", () => {
  const result = normalizeCodexModelSelector("CODEX", {
    ...config,
    models: [model("gpt-6-astra"), ...config.models],
  })!;
  assert.equal(result.models.filter((m) => m.id === "gpt-6-astra").length, 1);
  assert.equal(result.models[0].reasoning_options.length, 5);
});
test("preserves discovered future capabilities and other executors", () => {
  const astra = {
    ...model("gpt-6-astra"),
    reasoning_options: [{ id: "high", label: "High", is_default: true }],
  };
  assert.deepEqual(
    normalizeCodexModelSelector("CODEX", {
      ...config,
      models: [astra, model("gpt-7")],
    })!.models,
    [astra, model("gpt-7")],
  );
  assert.equal(normalizeCodexModelSelector("CLAUDE_CODE", config), config);
  assert.equal(normalizeCodexModelSelector("CODEX", null), null);
});

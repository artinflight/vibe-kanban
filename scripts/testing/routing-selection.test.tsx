import assert from "node:assert/strict";
import test from "node:test";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import { useExecutorConfig } from "../../packages/web-core/src/shared/hooks/useExecutorConfig";
import type { ExecutorConfig, ExecutorProfile } from "../../shared/types";

const automatic: ExecutorConfig = {
  executor: "CODEX",
  variant: "DEFAULT",
  model_id: "gpt-6.1-sol",
  reasoning_id: "medium",
  routing: {
    mode: "auto",
    floor: "workhorse",
    denied_models: [],
    allow_escalation: false,
  },
};
const profiles = {
  CODEX: { configurations: { DEFAULT: {} } },
} as unknown as Record<string, ExecutorProfile>;
let current: ReturnType<typeof useExecutorConfig>;
function Harness({ scratch, session }: { scratch?: ExecutorConfig; session?: ExecutorConfig }) {
  current = useExecutorConfig({
    profiles,
    lastUsedConfig: automatic,
    scratchConfig: scratch,
    sessionConfig: session,
  });
  return null;
}

test("unrelated last-used automatic choice never opts a new chat into routing", () => {
  let renderer: ReactTestRenderer;
  act(() => {
    renderer = create(<Harness />);
  });
  assert.equal(current.executorConfig?.routing, undefined);
  act(() => renderer!.unmount());
});
test("saved per-chat routing survives hydration, explicit model choice locks it", () => {
  let renderer: ReactTestRenderer;
  act(() => {
    renderer = create(<Harness scratch={automatic} />);
  });
  assert.equal(current.executorConfig?.routing?.mode, "auto");
  act(() =>
    current.setOverrides({ model_id: "gpt-6-astra", reasoning_id: "high" }),
  );
  assert.equal(current.executorConfig?.routing?.mode, "manual");
  assert.equal(current.executorConfig?.routing?.floor, "workhorse");
  assert.equal(current.executorConfig?.model_id, "gpt-6-astra");
  assert.equal(current.executorConfig?.reasoning_id, "high");
  act(() => renderer!.unmount());
});
test("explicit effort selection locks the model; routing can be re-enabled explicitly", () => {
  let renderer: ReactTestRenderer;
  act(() => {
    renderer = create(<Harness scratch={automatic} />);
  });
  act(() => current.setOverrides({ reasoning_id: "high" }));
  assert.equal(current.executorConfig?.routing?.mode, "manual");
  assert.equal(current.executorConfig?.reasoning_id, "high");
  act(() =>
    current.setOverrides({
      routing: { ...automatic.routing!, mode: "shadow" },
    }),
  );
  assert.equal(current.executorConfig?.routing?.mode, "shadow");
  assert.equal(current.executorConfig?.reasoning_id, "high");
  act(() => renderer!.unmount());
});

 test("manual lock retains hydrated exclusions and automatic minimum", () => {
  let renderer: ReactTestRenderer;
  const scratch = { ...automatic, routing: { ...automatic.routing!, floor: "assessed" as const, denied_models: ["gpt-6-astra"], allow_escalation: true } };
  act(() => { renderer = create(<Harness scratch={scratch} />); });
  act(() => current.setOverrides({ reasoning_id: "high" }));
  assert.equal(current.executorConfig?.routing?.mode, "manual");
  assert.equal(current.executorConfig?.routing?.floor, "assessed");
  assert.deepEqual(current.executorConfig?.routing?.denied_models, ["gpt-6-astra"]);
  assert.equal(current.executorConfig?.routing?.allow_escalation, true);
  act(() => renderer!.unmount());
});

for (const mode of ["shadow", "auto"] as const) {
  test(`${mode} survives a cleared draft and remount in the same session`, () => {
    let renderer: ReactTestRenderer;
    const session = { ...automatic, routing: { ...automatic.routing!, mode } };
    act(() => { renderer = create(<Harness scratch={session} session={session} />); });
    act(() => { renderer!.update(<Harness session={session} />); });
    assert.equal(current.executorConfig?.routing?.mode, mode);
    act(() => renderer!.unmount());
    act(() => { renderer = create(<Harness session={session} />); });
    assert.equal(current.executorConfig?.routing?.mode, mode);
    act(() => current.setOverrides({ reasoning_id: "high" }));
    assert.equal(current.executorConfig?.routing?.mode, "manual");
    act(() => renderer!.unmount());
  });
}
test("manual scratch and different profile remain authoritative over session routing", () => {
  let renderer: ReactTestRenderer;
  const manual = { ...automatic, routing: { ...automatic.routing!, mode: "manual" as const } };
  act(() => { renderer = create(<Harness scratch={manual} session={automatic} />); });
  assert.equal(current.executorConfig?.routing?.mode, "manual");
  act(() => renderer!.unmount());
  act(() => { renderer = create(<Harness session={{ ...automatic, variant: "OTHER" }} />); });
  assert.equal(current.executorConfig?.routing, undefined);
  act(() => renderer!.unmount());
});

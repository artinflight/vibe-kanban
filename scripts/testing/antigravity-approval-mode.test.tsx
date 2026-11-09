import assert from "node:assert/strict";
import test from "node:test";
import { act, create, type ReactTestRenderer } from "react-test-renderer";
import {
  getDefaultExecutorOverride,
  useExecutorConfig,
} from "../../packages/web-core/src/shared/hooks/useExecutorConfig";
import {
  BaseCodingAgent,
  type ExecutorConfig,
  type ExecutorProfile,
} from "../../shared/types";

const agProfiles = {
  ANTIGRAVITY: { configurations: { DEFAULT: {} } },
} as unknown as Record<string, ExecutorProfile>;

let current: ReturnType<typeof useExecutorConfig>;

function AgHarness({
  lastUsed,
  scratch,
  isNewSession,
}: {
  lastUsed: ExecutorConfig | null;
  scratch?: ExecutorConfig;
  isNewSession?: boolean;
}) {
  current = useExecutorConfig({
    profiles: agProfiles,
    lastUsedConfig: lastUsed,
    scratchConfig: scratch,
    isNewSession,
    preferPresetOverrides: isNewSession,
  });
  return null;
}

test("Antigravity approval mode defaults to SUPERVISED for legacy existing sessions and supports explicit AUTO selection", () => {
  assert.equal(
    getDefaultExecutorOverride(
      BaseCodingAgent.ANTIGRAVITY,
      "permission_policy",
    ),
    "SUPERVISED",
  );

  let renderer: ReactTestRenderer;
  // Legacy existing session without stored permission_policy stays explicitly SUPERVISED
  act(() => {
    renderer = create(
      <AgHarness
        lastUsed={{ executor: BaseCodingAgent.ANTIGRAVITY, variant: "DEFAULT" }}
        isNewSession={false}
      />,
    );
  });
  assert.equal(current.executorConfig?.permission_policy, "SUPERVISED");

  // Explicit user override switches the resumed session to AUTO
  act(() => current.setOverrides({ permission_policy: "AUTO" }));
  assert.equal(current.executorConfig?.permission_policy, "AUTO");
  act(() => renderer!.unmount());

  // Existing session that previously ran in AUTO preserves AUTO until explicitly switched back
  act(() => {
    renderer = create(
      <AgHarness
        lastUsed={{
          executor: BaseCodingAgent.ANTIGRAVITY,
          variant: "DEFAULT",
          permission_policy: "AUTO",
        }}
        isNewSession={false}
      />,
    );
  });
  assert.equal(current.executorConfig?.permission_policy, "AUTO");
  act(() => current.setOverrides({ permission_policy: "SUPERVISED" }));
  assert.equal(current.executorConfig?.permission_policy, "SUPERVISED");
  act(() => renderer!.unmount());

  // New session defaults to SUPERVISED and supports explicit AUTO selection
  act(() => {
    renderer = create(<AgHarness lastUsed={null} isNewSession={true} />);
  });
  assert.equal(current.executorConfig?.permission_policy, "SUPERVISED");
  act(() => current.setOverrides({ permission_policy: "AUTO" }));
  assert.equal(current.executorConfig?.permission_policy, "AUTO");
  act(() => renderer!.unmount());
});

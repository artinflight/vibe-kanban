import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { JSDOM } from "jsdom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import assert from "node:assert/strict";
import { after, afterEach, beforeEach, test } from "node:test";
import { ProjectRightSidebarContainer } from "../../packages/web-core/src/pages/kanban/ProjectRightSidebarContainer";
import { useMarkWorkspaceSeen } from "../../packages/web-core/src/shared/hooks/useMarkWorkspaceSeen";
import { useOpenProjectWorkspace } from "../../packages/web-core/src/shared/hooks/useOpenProjectWorkspace";
import { state } from "./workspace-seen.fixture";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  IS_REACT_ACT_ENVIRONMENT: true,
});
let visibility = "visible";
Object.defineProperty(document, "visibilityState", { get: () => visibility });
let root: Root;
let client: QueryClient;
let element: HTMLDivElement;
let invalidations: unknown[];
const project = () => (
  <ProjectRightSidebarContainer
    expectedIssueId={null}
    onExpectIssueOpen={() => {}}
  />
);
function Chat({ id }: { id?: string }) {
  useMarkWorkspaceSeen(id);
  return null;
}
async function render(child: React.ReactNode = project()) {
  await act(async () =>
    root.render(
      <QueryClientProvider client={client}>{child}</QueryClientProvider>,
    ),
  );
}
async function setVisibility(value: string) {
  visibility = value;
  await act(async () => {
    document.dispatchEvent(new dom.window.Event("visibilitychange"));
  });
}
beforeEach(() => {
  Object.assign(state, {
    workspaceId: "a",
    workspace: { id: "a" },
    loading: false,
    createIssue: false,
    createWorkspace: false,
    calls: [],
    fail: false,
    navigations: [],
  });
  visibility = "visible";
  invalidations = [];
  client = new QueryClient();
  client.invalidateQueries = async (filters) => {
    invalidations.push(filters);
  };
  element = document.createElement("div");
  document.body.append(element);
  root = createRoot(element);
});
afterEach(async () => {
  await act(async () => root.unmount());
  element.remove();
  client.clear();
});
after(() => dom.window.close());

test("opening project chat clears that workspace and refreshes summary badges", async () => {
  await render();
  assert.deepEqual(state.calls, ["a"]);
  assert.deepEqual(invalidations, [{ queryKey: ["workspace-summaries"] }]);
  // A fresh summary/record or session rerender must not consume a new completion.
  state.workspace = { id: "a" };
  await render();
  assert.deepEqual(state.calls, ["a"]);
});

test("loading, missing and mismatched records do not clear any workspace", async () => {
  state.loading = true;
  await render();
  state.loading = false;
  state.workspace = undefined;
  await render();
  state.workspace = { id: "sibling" };
  await render();
  assert.deepEqual(state.calls, []);
  state.workspace = { id: "a" };
  await render();
  assert.deepEqual(state.calls, ["a"]);
});

test("switching workspaces clears only the loaded destination and removes the old listener", async () => {
  await render();
  state.workspaceId = "b";
  state.loading = true;
  await render();
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a"]);
  state.loading = false;
  state.workspace = { id: "b" };
  await render();
  await setVisibility("hidden");
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a", "b", "b"]);
});

test("background project chat waits for visibility and stops clearing after closing", async () => {
  visibility = "hidden";
  await render();
  assert.deepEqual(state.calls, []);
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a"]);
  state.workspaceId = null;
  await render();
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a"]);
});

for (const mode of ["createIssue", "createWorkspace"] as const) {
  test(`${mode} does not mark a workspace read`, async () => {
    state[mode] = true;
    await render();
    assert.deepEqual(state.calls, []);
  });
}

test("shared Workspaces hook preserves panel visibility gating and reopening", async () => {
  await render(<Chat />);
  await setVisibility("visible");
  assert.deepEqual(state.calls, []);
  await render(<Chat id="a" />);
  await render(<Chat id="a" />);
  assert.deepEqual(state.calls, ["a"]);
  await render(<Chat />);
  await render(<Chat id="a" />);
  assert.deepEqual(state.calls, ["a", "a"]);
});

test("failed seen request leaves badges intact and can retry when returning", async () => {
  const warn = console.warn;
  const warnings: unknown[][] = [];
  console.warn = (...args) => warnings.push(args);
  try {
    state.fail = true;
    await render();
    assert.equal(warnings.length, 1);
    assert.deepEqual(invalidations, []);
    state.fail = false;
    await setVisibility("visible");
    assert.deepEqual(state.calls, ["a", "a"]);
    assert.equal(invalidations.length, 1);
  } finally {
    console.warn = warn;
  }
});

function WorkspaceLink({ projectId = "p", issueId = "issue", id = "a" }) {
  const open = useOpenProjectWorkspace();
  return (
    <button onClick={() => open(projectId, issueId, id)}>
      Open conversation
    </button>
  );
}
async function clickWorkspace() {
  await act(async () => {
    element.querySelector("button")!.click();
  });
}

test("reselecting the displayed project workspace reads again without requiring a route change", async () => {
  await render(<WorkspaceLink />);
  assert.deepEqual(state.calls, []);
  await clickWorkspace();
  await clickWorkspace();
  assert.deepEqual(state.calls, ["a", "a"]);
  assert.deepEqual(state.navigations, [
    ["p", "issue", "a"],
    ["p", "issue", "a"],
  ]);
  assert.equal(invalidations.length, 2);
  await render(<WorkspaceLink />);
  assert.deepEqual(
    state.calls,
    ["a", "a"],
    "Polling must not consume another completion",
  );
});

for (const props of [
  { id: "sibling" },
  { issueId: "other" },
  { projectId: "other" },
]) {
  test(`navigation to ${JSON.stringify(props)} waits for destination chat visibility`, async () => {
    await render(<WorkspaceLink {...props} />);
    await clickWorkspace();
    assert.deepEqual(state.calls, []);
    assert.equal(state.navigations.length, 1);
  });
}

test("background or issue-create state does not clear the previously selected workspace", async () => {
  visibility = "hidden";
  await render(<WorkspaceLink />);
  await clickWorkspace();
  visibility = "visible";
  state.createIssue = true;
  await render(<WorkspaceLink />);
  await clickWorkspace();
  assert.deepEqual(state.calls, []);
});

import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { JSDOM } from "jsdom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import assert from "node:assert/strict";
import { after, afterEach, beforeEach, test } from "node:test";
import { ProjectRightSidebarContainer } from "../../packages/web-core/src/pages/kanban/ProjectRightSidebarContainer";
import { WorkspaceReadControls } from "../../packages/web-core/src/shared/components/WorkspaceReadControls";
import { WorkspacesMainContainer } from "../../packages/web-core/src/pages/workspaces/WorkspacesMainContainer";
import { useOpenProjectWorkspace } from "../../packages/web-core/src/shared/hooks/useOpenProjectWorkspace";
import { state } from "./workspace-seen.fixture";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  CustomEvent: dom.window.CustomEvent,
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
    pause: undefined,
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


const readButton = () => element.querySelector<HTMLButtonElement>('button[title^="Mark all agent replies"]');
async function clickRead() {
  assert(readButton(), "Explicit workspace read control must be available");
  await act(async () => { readButton()!.click(); });
}
function WorkspacesChat({ id = "a" }) {
  return <WorkspacesMainContainer
    selectedWorkspace={{ id } as never}
    selectedSession={undefined}
    selectedSessionId={undefined}
    sessions={[]}
    repos={[]}
    onSelectSession={() => {}}
    isLoading={false}
    isSessionsLoading={true}
    isNewSessionMode={false}
    onStartNewSession={() => {}}
  />;
}

test("workspace record/polling without a rendered transcript preserves unread", async () => {
  await render();
  assert.deepEqual(state.calls, []);
  state.workspace = { id: "a" };
  await render();
  await setVisibility("hidden");
  await setVisibility("visible");
  assert.deepEqual(state.calls, []);
  await clickRead();
  assert.deepEqual(state.calls, ["a"]);
  assert.deepEqual(invalidations, [{ queryKey: ["workspace-summaries"] }]);
});

test("loading, missing and mismatched project records cannot expose a read action", async () => {
  state.loading = true;
  await render();
  assert.equal(readButton(), null);
  state.loading = false;
  state.workspace = undefined;
  await render();
  assert.equal(readButton(), null);
  state.workspace = { id: "sibling" };
  await render();
  assert.equal(readButton(), null);
  assert.deepEqual(state.calls, []);
  state.workspace = { id: "a" };
  await render();
  assert(readButton());
  assert.deepEqual(state.calls, []);
});

test("switching workspaces and returning to a tab never acknowledge either workspace", async () => {
  await render();
  state.workspaceId = "b";
  state.loading = true;
  await render();
  await setVisibility("visible");
  state.loading = false;
  state.workspace = { id: "b" };
  await render();
  await setVisibility("hidden");
  await setVisibility("visible");
  assert.deepEqual(state.calls, []);
  await clickRead();
  assert.deepEqual(state.calls, ["b"]);
});

test("background project chat and closing/reopening preserve unread", async () => {
  visibility = "hidden";
  await render();
  await setVisibility("visible");
  state.workspaceId = null;
  await render();
  state.workspaceId = "a";
  await render();
  assert.deepEqual(state.calls, []);
});

for (const mode of ["createIssue", "createWorkspace"] as const) {
  test(`${mode} does not mark a workspace read or show its read action`, async () => {
    state[mode] = true;
    await render();
    assert.deepEqual(state.calls, []);
    assert.equal(readButton(), null);
  });
}

test("Workspaces chat stays unread during loading, remounts, visibility and session rerenders", async () => {
  await render(<WorkspacesChat />);
  await render(<WorkspacesChat />);
  await setVisibility("hidden");
  await setVisibility("visible");
  await render(<div />);
  await render(<WorkspacesChat />);
  assert.deepEqual(state.calls, []);
  await clickRead();
  assert.deepEqual(state.calls, ["a"]);
});

test("a new completion after an explicit read stays unread through rerenders and tab return", async () => {
  await render();
  await clickRead();
  // A subsequent completion changes summaries/records, not user intent.
  state.workspace = { id: "a" };
  await render();
  await setVisibility("hidden");
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a"]);
});

test("manual unread is preserved on remount/return until another explicit read", async () => {
  await render(<WorkspaceReadControls key="a" workspaceId="a" />);
  await clickRead();
  // The backend may now have a manual unread hold. No automatic follow-up is allowed.
  await render(<div />);
  await render(<WorkspaceReadControls key="a" workspaceId="a" />);
  await setVisibility("hidden");
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a"]);
  await clickRead();
  assert.deepEqual(state.calls, ["a", "a"]);
});

test("failed explicit read shows an error without badge invalidation or automatic retry", async () => {
  state.fail = true;
  await render();
  await clickRead();
  assert(element.querySelector('[role="alert"]'));
  assert.deepEqual(invalidations, []);
  state.fail = false;
  await setVisibility("hidden");
  await setVisibility("visible");
  assert.deepEqual(state.calls, ["a"]);
  await clickRead();
  assert.deepEqual(state.calls, ["a", "a"]);
  assert.equal(element.querySelector('[role="alert"]'), null);
  assert.equal(invalidations.length, 1);
});

test("pending explicit read disables duplicate clicks", async () => {
  let release!: () => void;
  state.pause = new Promise<void>((resolve) => { release = resolve; });
  await render();
  await clickRead();
  assert.equal(readButton()!.disabled, true);
  await clickRead();
  assert.deepEqual(state.calls, ["a"]);
  await act(async () => { release(); });
  assert.equal(readButton()!.disabled, false);
});

test("an old request cannot show its error in a newly selected workspace", async () => {
  let release!: () => void;
  state.pause = new Promise<void>((resolve) => { release = resolve; });
  await render(<WorkspaceReadControls key="a" workspaceId="a" />);
  await clickRead();
  await render(<WorkspaceReadControls key="b" workspaceId="b" />);
  state.fail = true;
  await act(async () => { release(); });
  assert.equal(element.querySelector('[role="alert"]'), null);
  assert.equal(readButton()!.disabled, false);
  assert.deepEqual(state.calls, ["a"]);
});

function WorkspaceLink({ projectId = "p", issueId = "issue", id = "a" }) {
  const open = useOpenProjectWorkspace();
  return <button onClick={() => open(projectId, issueId, id)}>Open conversation</button>;
}
async function clickWorkspace() {
  await act(async () => { element.querySelector("button")!.click(); });
}

test("same-route project reselection defers reading to the displayed transcript", async () => {
  await render(<WorkspaceLink />);
  await clickWorkspace();
  await clickWorkspace();
  assert.deepEqual(state.calls, []);
  assert.deepEqual(state.navigations, [["p", "issue", "a"], ["p", "issue", "a"]]);
  assert.deepEqual(invalidations, []);
});

for (const props of [{ id: "sibling" }, { issueId: "other" }, { projectId: "other" }]) {
  test(`navigation to ${JSON.stringify(props)} preserves unread`, async () => {
    await render(<WorkspaceLink {...props} />);
    await clickWorkspace();
    assert.deepEqual(state.calls, []);
    assert.equal(state.navigations.length, 1);
  });
}

test("reselection while the workspace record is loading preserves unread", async () => {
  state.loading = true;
  state.workspace = undefined;
  await render(<WorkspaceLink />);
  await clickWorkspace();
  assert.deepEqual(state.calls, []);
});

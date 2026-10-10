import React from "react";
import { act, create } from "react-test-renderer";
import assert from "node:assert/strict";
import { test } from "node:test";
import { ExecutionProcessesContext } from "../../packages/web-core/src/shared/hooks/useExecutionProcessesContext";
import { setLocalApiTransport } from "../../packages/web-core/src/shared/lib/localApiTransport";
import { useConversationHistory } from "../../packages/web-core/src/features/workspace-chat/model/hooks/useConversationHistory";

globalThis.window = globalThis;
globalThis.requestAnimationFrame = (callback) => setTimeout(callback, 0);
globalThis.cancelAnimationFrame = clearTimeout;
class MockSocket {
  listeners = new Map();
  closed = false;
  addEventListener(type, callback) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(callback);
  }
  emit(type, event) {
    for (const callback of this.listeners.get(type) ?? []) callback(event);
  }
  message(value) {
    this.emit("message", { data: JSON.stringify(value) });
  }
  close() {
    this.closed = true;
    this.emit("close");
  }
}

const process = (id, status = "completed") => ({
  id,
  status,
  run_reason: "codingagent",
  created_at: id,
  updated_at: id,
  executor_action: { typ: { type: "CodingAgentInitialRequest" } },
});
const pageResponse = (total, before, limit) => {
  const end = before ?? total;
  const start = Math.max(0, end - limit);
  return new Response(
    JSON.stringify({
      success: true,
      data: {
        entries: Array.from({ length: end - start }, (_, i) => ({
          index: start + i,
          entry: { type: "STDOUT", content: String(start + i) },
        })),
        next_before: start || null,
      },
    }),
    { headers: { "content-type": "application/json" } },
  );
};
const settle = async () => {
  for (let i = 0; i < 8; i++) await Promise.resolve();
};

function harness(initialProcesses, request, allowLive = false) {
  const sockets = [];
  let result;
  let timeline;
  let renderer;
  let current = initialProcesses;
  let scope = "one";
  const calls = [];
  setLocalApiTransport({
    request: async (url, options) => {
      const parsed = new URL(url, "http://test");
      calls.push({
        id: parsed.pathname.split("/")[3],
        before: parsed.searchParams.has("before")
          ? Number(parsed.searchParams.get("before"))
          : null,
        limit: Number(parsed.searchParams.get("limit")),
        signal: options.signal,
      });
      return request(calls.at(-1), calls.length);
    },
    openWebSocket: () => {
      if (!allowLive)
        throw new Error("Completed history must not open replay sockets");
      const socket = new MockSocket();
      sockets.push(socket);
      return socket;
    },
  });
  function Probe() {
    result = useConversationHistory({
      scopeKey: scope,
      onTimelineUpdated: (value) => {
        timeline = value;
      },
    });
    return null;
  }
  const view = () => (
    <ExecutionProcessesContext.Provider
      value={{
        executionProcessesVisible: current,
        isLoading: false,
        isConnected: true,
      }}
    >
      <Probe />
    </ExecutionProcessesContext.Provider>
  );
  return {
    calls,
    sockets,
    async mount() {
      await act(async () => {
        renderer = create(view());
        await settle();
      });
    },
    async load() {
      await act(async () => {
        await result.loadMoreHistory();
        await settle();
      });
    },
    async update(next, nextScope = scope) {
      current = next;
      scope = nextScope;
      await act(async () => {
        renderer.update(view());
        await settle();
      });
    },
    async close() {
      await act(async () => renderer.unmount());
      setLocalApiTransport(null);
    },
    get result() {
      return result;
    },
    get entries() {
      return Object.values(timeline?.executionProcessState ?? {}).flatMap(
        (p) => p.entries,
      );
    },
  };
}

test("10,000-entry turn opens with 40 entries, loads older once, and retains row keys", async () => {
  const h = harness([process("a"), process("b")], ({ before, limit }) =>
    pageResponse(10_000, before, limit),
  );
  try {
    await h.mount();
    assert.equal(h.calls.length, 1);
    assert.equal(h.calls[0].id, "b");
    assert.equal(h.entries.length, 40);
    assert.equal(h.entries[0].patchKey, "b:9960");
    assert.equal(h.entries.at(-1).patchKey, "b:9999");
    assert.equal(h.result.hasMoreHistory, true);
    await act(async () => {
      await Promise.all([
        h.result.loadMoreHistory(),
        h.result.loadMoreHistory(),
      ]);
    });
    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].before, 9960);
    assert.equal(h.entries.length, 90);
    assert.equal(new Set(h.entries.map((e) => e.patchKey)).size, 90);
    assert.equal(h.entries.at(-1).patchKey, "b:9999");
  } finally {
    await h.close();
  }
});

test("pages across turns without refetching already loaded turns", async () => {
  const h = harness([process("a"), process("b")], ({ id, before, limit }) =>
    pageResponse(id === "b" ? 10 : 75, before, limit),
  );
  try {
    await h.mount();
    assert.deepEqual(
      h.calls.map((c) => [c.id, c.limit]),
      [
        ["b", 40],
        ["a", 30],
      ],
    );
    assert.equal(h.entries.length, 40);
    await h.load();
    assert.deepEqual(
      h.calls.map((c) => c.id),
      ["b", "a", "a"],
    );
    assert.equal(h.entries.length, 85);
    assert.equal(h.result.hasMoreHistory, false);
    await h.load();
    assert.equal(h.calls.length, 3);
  } finally {
    await h.close();
  }
});

test("failure stops loading and retries without an automatic request loop", async () => {
  const h = harness([process("a")], ({ before, limit }, count) => {
    if (count === 1) throw new Error("offline");
    return pageResponse(100, before, limit);
  });
  try {
    await h.mount();
    assert.equal(h.calls.length, 1);
    assert.equal(h.result.historyError, true);
    assert.equal(h.result.isLoadingHistory, false);
    await h.load();
    assert.equal(h.entries.length, 40);
    assert.equal(h.result.historyError, false);
  } finally {
    await h.close();
  }
});

test("switching workspace aborts requests and ignores a late response", async () => {
  let resolveOld;
  const h = harness([process("a")], ({ id, before, limit }) =>
    id === "a"
      ? new Promise((resolve) => {
          resolveOld = resolve;
        })
      : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    await h.update([process("b")], "two");
    assert.equal(h.calls[0].signal.aborted, true);
    await act(async () => {
      resolveOld(pageResponse(100, null, 40));
      await settle();
    });
    assert.equal(h.entries.length, 10);
    assert.ok(h.entries.every((e) => e.executionProcessId === "b"));
    assert.equal(h.result.isLoadingHistory, false);
  } finally {
    await h.close();
  }
});

test("completed follow-up discovered after hydration appears without reopening history", async () => {
  const h = harness([process("a")], ({ before, limit }) =>
    pageResponse(100, before, limit),
  );
  try {
    await h.mount();
    await h.update([process("a"), process("b")]);
    assert.equal(h.calls.length, 2);
    assert.equal(h.calls[1].id, "b");
    assert.equal(h.entries.length, 80);
    await h.update([process("b")]);
    assert.equal(h.entries.length, 40);
  } finally {
    await h.close();
  }
});

test("completion during a partial live replay keeps missing older pages available", async () => {
  const h = harness(
    [process("a", "running")],
    ({ before, limit }) => pageResponse(100, before, limit),
    true,
  );
  try {
    await h.mount();
    assert.equal(h.calls.length, 0);
    assert.equal(h.sockets.length, 1);
    await act(async () => {
      h.sockets[0].emit("open");
      h.sockets[0].message({
        JsonPatch: [
          {
            op: "add",
            path: "/entries/0",
            value: { type: "STDOUT", content: "0" },
          },
        ],
      });
      await new Promise((resolve) => setTimeout(resolve, 10));
    });
    assert.equal(h.entries.length, 1);
    await h.update([process("a")]);
    assert.equal(h.entries.length, 41);
    assert.equal(h.result.hasMoreHistory, true);
    await h.load();
    await h.load();
    assert.equal(h.entries.length, 100);
    assert.equal(h.result.hasMoreHistory, false);
    await h.update([], "other");
    assert.equal(h.sockets[0].closed, true);
    assert.equal(h.entries.length, 0);
  } finally {
    await h.close();
  }
});

test("a new completed turn arriving during initial history loading is retained", async () => {
  let resolveOld;
  const h = harness([process("a")], ({ id, before, limit }) =>
    id === "a"
      ? new Promise((resolve) => {
          resolveOld = resolve;
        })
      : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    await h.update([process("a"), process("b")]);
    await act(async () => {
      resolveOld(pageResponse(100, null, 40));
      await settle();
    });
    assert.deepEqual(
      h.calls.map((c) => c.id),
      ["a", "b"],
    );
    assert.equal(h.entries.length, 50);
  } finally {
    await h.close();
  }
});

test("an initially empty process list hydrates only the newest page when history arrives", async () => {
  const h = harness([], ({ before, limit }) =>
    pageResponse(100, before, limit),
  );
  try {
    await h.mount();
    assert.equal(h.calls.length, 0);
    await h.update([process("a"), process("b"), process("c")]);
    assert.deepEqual(
      h.calls.map((c) => c.id),
      ["c"],
    );
    assert.equal(h.entries.length, 40);
  } finally {
    await h.close();
  }
});

test("incomplete capture is visible and does not load older status as current", async () => {
  const h = harness(
    [
      { ...process("old"), created_at: "2026-10-09T20:00:00Z" },
      { ...process("new"), created_at: "2026-10-09T21:00:00Z" },
    ],
    ({ id, before, limit }) =>
      id === "new"
        ? new Response(
            JSON.stringify({
              success: true,
              data: {
                entries: [],
                next_before: null,
                capture_error: "Incomplete native capture",
              },
            }),
            { headers: { "content-type": "application/json" } },
          )
        : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    assert.equal(h.result.historyError, true);
    assert.equal(h.entries.length, 0);
    assert.deepEqual(
      h.calls.map((x) => x.id),
      ["new"],
    );
  } finally {
    await h.close();
  }
});

test("unavailable capture clears only after a new authoritative retry succeeds", async () => {
  const h = harness([process("new")], ({ before, limit }, call) =>
    call === 1
      ? new Response(
          JSON.stringify({
            success: true,
            data: {
              entries: [],
              next_before: null,
              capture_error: "Capture pending",
            },
          }),
          { headers: { "content-type": "application/json" } },
        )
      : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    assert.equal(h.result.historyError, true);
    assert.match(h.result.historyErrorDetail, /completeness/);
    await h.load();
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.historyErrorDetail, null);
    assert.equal(h.entries.length, 10);
  } finally {
    await h.close();
  }
});

test("a late unavailable response cannot contaminate another workspace", async () => {
  let resolveOld;
  const h = harness([process("old")], ({ id, before, limit }) =>
    id === "old"
      ? new Promise((resolve) => {
          resolveOld = resolve;
        })
      : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    await h.update([process("new")], "another-workspace");
    await act(async () => {
      resolveOld(
        new Response(
          JSON.stringify({
            success: true,
            data: {
              entries: [],
              next_before: null,
              capture_error: "Old capture pending",
            },
          }),
          { headers: { "content-type": "application/json" } },
        ),
      );
      await settle();
    });
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.historyErrorDetail, null);
    assert.equal(h.entries.length, 10);
  } finally {
    await h.close();
  }
});

const pendingResponse = () =>
  new Response(
    JSON.stringify({
      success: true,
      data: {
        entries: [],
        next_before: null,
        capture_pending: true,
        capture_error: null,
      },
    }),
    { headers: { "content-type": "application/json" } },
  );
const failedCaptureResponse = () =>
  new Response(
    JSON.stringify({
      success: true,
      data: {
        entries: [],
        next_before: null,
        capture_pending: false,
        capture_error: "Incomplete capture",
      },
    }),
    { headers: { "content-type": "application/json" } },
  );

async function tickCapture(t) {
  await act(async () => {
    t.mock.timers.tick(1000);
    await settle();
  });
}

for (const pending of [false, true]) {
  test(`older completion${pending ? " after pending retry" : ""} preserves a newer terminal capture warning`, async (t) => {
    t.mock.timers.enable({ apis: ["setTimeout"] });
    const newer = {
      ...process("a", "running"),
      created_at: "2026-10-09T21:00:00Z",
    };
    const older = {
      ...process("b", "running"),
      created_at: "2026-10-09T20:00:00Z",
    };
    let newerDamaged = true;
    let olderCalls = 0;
    const h = harness(
      [older, newer],
      ({ id, before, limit }) => {
        if (id === "a" && newerDamaged) return failedCaptureResponse();
        if (id === "b" && ++olderCalls === 1 && pending)
          return pendingResponse();
        return pageResponse(id === "a" ? 40 : 10, before, limit);
      },
      true,
    );
    try {
      await h.mount();
      assert.equal(h.calls.length, 0);
      const completedNewer = { ...newer, status: "completed" };
      await h.update([older, completedNewer]);
      assert.deepEqual(
        h.calls.map((x) => x.id),
        ["a"],
      );
      assert.equal(h.result.historyError, true);
      const warning = h.result.historyErrorDetail;
      assert.match(warning, /completeness/);

      await h.update([{ ...older, status: "completed" }, completedNewer]);
      assert.deepEqual(
        h.calls.map((x) => x.id),
        ["a", "b"],
      );
      assert.equal(h.result.historyError, true);
      assert.equal(h.result.historyErrorDetail, warning);
      assert.equal(h.result.isLoadingHistory, pending);
      if (pending) await tickCapture(t);
      assert.equal(h.entries.length, 10);
      assert.ok(h.entries.every((entry) => entry.executionProcessId === "b"));
      assert.equal(h.result.historyError, true);
      assert.equal(h.result.historyErrorDetail, warning);
      assert.equal(h.result.isLoadingHistory, false);
      const callsAfterClosure = h.calls.length;
      await tickCapture(t);
      assert.equal(h.calls.length, callsAfterClosure, "Closed B stops polling");

      newerDamaged = false;
      await h.load();
      assert.equal(h.calls.at(-1).id, "a", "Retry reads the warned execution");
      assert.equal(h.result.historyError, false);
      assert.equal(h.result.historyErrorDetail, null);
      assert.equal(h.entries.length, 50);
    } finally {
      await h.close();
      t.mock.timers.reset();
    }
  });
}

test("removing an unavailable execution clears only its scoped error", async () => {
  const h = harness([process("a")], ({ id, before, limit }) =>
    id === "a" ? failedCaptureResponse() : pageResponse(40, before, limit),
  );
  try {
    await h.mount();
    assert.equal(h.result.historyError, true);
    await h.update([process("b")]);
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.historyErrorDetail, null);
    assert.equal(h.entries.length, 40);
    assert.ok(h.entries.every((entry) => entry.executionProcessId === "b"));
  } finally {
    await h.close();
  }
});

test("running then completed then pending then closed recovers without manual retry", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = harness(
    [process("a", "running")],
    ({ before, limit }, call) =>
      call < 3 ? pendingResponse() : pageResponse(10, before, limit),
    true,
  );
  try {
    await h.mount();
    assert.equal(h.calls.length, 0);
    await h.update([process("a")]);
    assert.equal(h.calls.length, 1);
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.isLoadingHistory, true);
    await tickCapture(t);
    assert.equal(h.calls.length, 2);
    assert.equal(h.result.historyError, false);
    await tickCapture(t);
    assert.equal(h.calls.length, 3);
    assert.equal(h.entries.length, 10);
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.historyErrorDetail, null);
    assert.equal(h.result.isLoadingHistory, false);
    await tickCapture(t);
    assert.equal(h.calls.length, 3, "Closed capture stops polling");
  } finally {
    await h.close();
    t.mock.timers.reset();
  }
});

test("initial pending capture retries at one-second boundaries without a request loop", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = harness([process("a")], ({ before, limit }, call) =>
    call === 1 ? pendingResponse() : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    assert.equal(h.calls.length, 1);
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.isLoadingHistory, true);
    await tickCapture(t);
    assert.equal(h.calls.length, 2);
    assert.equal(h.entries.length, 10);
    assert.equal(h.result.isLoadingHistory, false);
    assert.equal(h.result.historyError, false);
  } finally {
    await h.close();
    t.mock.timers.reset();
  }
});

test("pending to terminal capture failure warns and stops automatic retries", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = harness([process("a")], (_, call) =>
    call === 1 ? pendingResponse() : failedCaptureResponse(),
  );
  try {
    await h.mount();
    await tickCapture(t);
    assert.equal(h.calls.length, 2);
    assert.equal(h.result.historyError, true);
    assert.equal(h.result.isLoadingHistory, false);
    assert.match(h.result.historyErrorDetail, /completeness/);
    await tickCapture(t);
    assert.equal(h.calls.length, 2);
  } finally {
    await h.close();
    t.mock.timers.reset();
  }
});

test("pending capture timer is cancelled when switching workspace", async (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const h = harness([process("a")], ({ id, before, limit }) =>
    id === "a" ? pendingResponse() : pageResponse(10, before, limit),
  );
  try {
    await h.mount();
    await h.update([process("b")], "different-workspace");
    assert.deepEqual(
      h.calls.map((x) => x.id),
      ["a", "b"],
    );
    await tickCapture(t);
    assert.deepEqual(
      h.calls.map((x) => x.id),
      ["a", "b"],
    );
    assert.equal(h.entries.length, 10);
    assert.equal(h.result.historyError, false);
    assert.equal(h.result.isLoadingHistory, false);
  } finally {
    await h.close();
    t.mock.timers.reset();
  }
});

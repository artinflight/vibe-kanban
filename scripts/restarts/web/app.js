/* The controller is the authority. Clocks never advance a progress bar. */
const $ = (id) => document.getElementById(id);
const labels = {
  pending: "Pending",
  running: "In progress",
  completed: "Completed",
  blocked: "Waiting",
  failed: "Failed",
  skipped: "Skipped",
  idle: "Waiting",
};
const fmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
let last = null;
let connectionLost = false;
let latestSource = null;
const resetKey = "vibe.restart-monitor.dismissed-run.v1";
let dismissedRun = null;
try {
  dismissedRun = localStorage.getItem(resetKey);
} catch {
  // A browser that blocks storage can still reset the current page.
}

function rememberReset(runId) {
  dismissedRun = runId;
  try {
    if (runId) localStorage.setItem(resetKey, runId);
    else localStorage.removeItem(resetKey);
  } catch {
    // Keep the in-memory reset usable when persistent storage is unavailable.
  }
}
function waitingForNext(source) {
  return {
    schema: 1,
    status: "idle",
    title: "Ready for the next restart",
    reset_pending: true,
    run_id: null,
    current_step: null,
    started_at: null,
    updated_at: null,
    percent: 0,
    completed_steps: 0,
    skipped_steps: 0,
    remaining_steps: source.steps.length,
    steps: source.steps.map(({ id, label }) => ({
      id,
      label,
      status: "pending",
      percent: 0,
    })),
    errors: [],
    blockers: [],
    events: [],
    estimate: null,
    source: "Waiting for a new controller attempt",
    source_error: source.source_error,
  };
}
function acceptSnapshot(value) {
  latestSource = value;
  if (dismissedRun && value.run_id && value.run_id !== dismissedRun)
    rememberReset(null);
  last = dismissedRun ? waitingForNext(value) : value;
  render(last);
}
function restartMonitor() {
  if (
    !latestSource?.run_id ||
    !["completed", "failed"].includes(latestSource.status)
  )
    return;
  rememberReset(latestSource.run_id);
  last = waitingForNext(latestSource);
  render(last);
}

function duration(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  if (seconds < 60) return `${Math.max(0, Math.ceil(seconds))}s`;
  const minutes = Math.ceil(seconds / 60);
  return minutes < 60
    ? `${minutes}m`
    : `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}
function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined) item.textContent = text;
  return item;
}
function renderEstimate(value) {
  const estimate = value.estimate;
  const terminal = value.status === "completed";
  if (!estimate) {
    $("eta").textContent = value.reset_pending
      ? "Waiting for next attempt"
      : "Waiting for an attempt";
    $("eta-note").textContent = "No restart plan received.";
    $("estimate-confidence").textContent = "Waiting";
    $("estimate-confidence").className = "badge";
    $("estimate-reason").textContent =
      "A new controller attempt will provide fresh progress and estimates.";
    $("estimate-assumptions").replaceChildren();
    $("estimate-as-of").textContent = "";
    $("estimate-checkpoint").textContent =
      "Next checkpoint: a new controller attempt is reported.";
    return;
  }
  $("eta").textContent = terminal
    ? "Complete"
    : estimate.upper_seconds === null
      ? "Not yet measurable"
      : `${duration(estimate.lower_seconds)}–${duration(estimate.upper_seconds)}`;
  const stale = estimate.stale || value.stale || connectionLost;
  $("eta-note").textContent = terminal
    ? "All restart checks passed."
    : estimate.upper_seconds === null
      ? estimate.confidence_reason
      : `${estimate.basis} range for ${estimate.scope || "remaining restart"}; conditional${stale ? " · last forecast retained" : ""}.`;
  const confidence = stale && !terminal ? "low" : estimate.confidence;
  $("estimate-confidence").textContent =
    `${confidence[0].toUpperCase()}${confidence.slice(1)} confidence`;
  $("estimate-confidence").className =
    `badge${confidence === "low" ? " blocked" : ""}`;
  $("estimate-reason").textContent =
    `${connectionLost ? "Disconnected: this forecast cannot be refreshed. " : ""}${estimate.confidence_reason}`;
  $("estimate-assumptions").replaceChildren(
    ...estimate.assumptions.map((assumption) => node("li", "", assumption)),
  );
  $("estimate-as-of").textContent =
    `Evidence as of ${new Date(estimate.as_of * 1000).toLocaleString()}${stale ? " · stale or unavailable observations" : ""}.`;
  const checkpoint = estimate.recalibration;
  $("estimate-checkpoint").textContent = checkpoint
    ? `Next recalibration: ${checkpoint.trigger}. Review ${Date.now() / 1000 >= checkpoint.due_at ? "overdue since" : "due at"} ${new Date(checkpoint.due_at * 1000).toLocaleTimeString()}.`
    : "Final controller completion recorded.";
}
function render(value) {
  const current = value.steps.find((step) => step.id === value.current_step);
  const terminal = value.status === "completed";
  $("restart-monitor").disabled =
    value.reset_pending ||
    !latestSource?.run_id ||
    !["completed", "failed"].includes(latestSource.status);
  $("restart-monitor").title = value.reset_pending
    ? "Already waiting at 0% for the next controller attempt"
    : ["running", "blocked"].includes(latestSource?.status)
      ? "Current restart is active or blocked; clear the monitor after it finishes"
      : "Clear a finished attempt from this browser and wait at 0% for the next restart";
  $("run-status").textContent = labels[value.status] || value.status;
  $("run-status").className = `badge ${value.status}`;
  $("stage-title").textContent = value.reset_pending
    ? "Waiting for the next restart"
    : terminal
      ? "Restart complete"
      : current?.label ||
        (value.status === "idle"
          ? "Waiting for controller updates"
          : "Restart needs attention");
  $("stage-detail").textContent = value.reset_pending
    ? "Monitor cleared. Progress starts when a new controller attempt is reported."
    : terminal
      ? value.published_at
        ? `Published ${new Date(value.published_at).toLocaleString()}; controller acceptance checks passed.`
        : "The controller has completed every restart step and verified Vibe."
      : current?.detail || "Waiting for the next controller observation.";
  $("step-count").textContent = value.steps.length
    ? `${value.completed_steps} of ${value.steps.length} steps completed${value.skipped_steps ? ` · ${value.skipped_steps} skipped` : ""}`
    : "No attempt selected";
  $("overall-percent").textContent =
    value.steps.length || value.reset_pending ? `${value.percent}%` : "—";
  $("overall-progress").value = value.percent;
  $("remaining").textContent = `${value.remaining_steps} remaining`;
  renderEstimate(value);
  $("run-title").textContent = value.title || "Vibe restart";
  $("source").textContent =
    `${value.source || "Restart controller"}${value.run_id ? ` · ${value.run_id}` : ""}`;
  $("steps").replaceChildren(
    ...value.steps.map((step, index) => {
      const row = node("li", `step ${step.status}`);
      row.append(
        node(
          "span",
          "step-icon",
          step.status === "completed"
            ? "✓"
            : step.status === "failed" || step.status === "blocked"
              ? "!"
              : String(index + 1),
        ),
      );
      if (step.id === value.current_step)
        row.setAttribute("aria-current", "step");
      const content = node("div", "step-content");
      const heading = node("div", "step-title");
      heading.append(
        node("h3", "", step.label),
        node(
          "span",
          "step-label",
          step.status === "completed" && step.duration_seconds
            ? duration(step.duration_seconds)
            : labels[step.status],
        ),
      );
      content.append(heading);
      if (step.detail) content.append(node("p", "step-detail", step.detail));
      if (step.metric || step.status === "running") {
        const bar = node("progress");
        bar.max = 100;
        if (step.percent !== null && step.percent !== undefined)
          bar.value = step.percent;
        bar.setAttribute("aria-label", `${step.label} progress`);
        content.append(bar);
      }
      if (step.metric) {
        const metric = step.metric;
        const text = `${fmt.format(metric.done)}${metric.total ? ` / ${metric.estimated_total ? "≈ " : ""}${fmt.format(metric.total)}` : ""} ${metric.unit}`;
        content.append(node("p", "step-metric", text));
      }
      row.append(content);
      return row;
    }),
  );
  if (!value.steps.length)
    $("steps").append(node("li", "empty", "Waiting for a restart plan."));
  const problems = [
    ...(value.errors || []).map((error) => ({
      title: error.kind || "Controller error",
      message: error.message,
    })),
    ...(value.blockers || []).map((message) => ({ title: "Blocker", message })),
  ];
  $("attention-count").textContent = String(problems.length);
  $("attention-content").replaceChildren(
    ...problems.map((problem) => {
      const box = node("div", "problem");
      box.append(node("h3", "", problem.title), node("p", "", problem.message));
      return box;
    }),
  );
  if (!problems.length)
    $("attention-content").append(
      node(
        "p",
        "clear",
        value.status === "idle"
          ? "Waiting for controller updates."
          : "✓  No errors or blockers reported.",
      ),
    );
  $("events").replaceChildren(
    ...(value.events || [])
      .slice(-6)
      .reverse()
      .map((event) => {
        const row = node("li", "", event.message);
        row.prepend(
          node("time", "", new Date(event.at * 1000).toLocaleTimeString()),
        );
        return row;
      }),
  );
  if (!(value.events || []).length && value.controller_phase)
    $("events").append(
      node("li", "", value.controller_phase.replaceAll("-", " ")),
    );
  const warning =
    value.source_error ||
    (value.stale
      ? "Controller observations are delayed. Progress is held at the last measurement; the conditional forecast remains visible with low confidence."
      : "");
  notice(warning);
  $("connection").className = `connection${warning ? " warning" : ""}`;
  $("connection").replaceChildren(
    node("span", "dot"),
    document.createTextNode(
      warning
        ? "Updates delayed"
        : value.reset_pending
          ? "Waiting for next attempt"
          : terminal
            ? "Verified complete"
            : "Receiving updates",
    ),
  );
  tick();
}
function notice(message) {
  $("notice").hidden = !message;
  $("notice").textContent = message;
}
function tick() {
  if (!last) return;
  const now = Date.now() / 1000;
  $("elapsed").textContent = last.started_at
    ? duration(
        (["completed", "failed"].includes(last.status)
          ? last.updated_at
          : now) - last.started_at,
      )
    : last.reset_pending
      ? "0s"
      : "—";
  const age = last.updated_at ? Math.max(0, now - last.updated_at) : null;
  $("updated").textContent =
    age === null ? "—" : age < 3 ? "Just now" : `${duration(age)} ago`;
  $("updated").title = last.updated_at
    ? new Date(last.updated_at * 1000).toLocaleString()
    : "";
  renderEstimate(last);
}
async function poll() {
  try {
    const response = await fetch("/api/status", {
      cache: "no-store",
      signal: AbortSignal.timeout(6000),
    });
    if (!response.ok) throw new Error("Unavailable");
    const value = await response.json();
    if (value.schema !== 1 || !Array.isArray(value.steps))
      throw new Error("Invalid update");
    connectionLost = false;
    acceptSnapshot(value);
  } catch {
    notice(
      "The monitor connection is unavailable. Showing the last received state and conditional forecast with low confidence; retrying automatically.",
    );
    $("connection").className = "connection warning";
    $("connection").replaceChildren(
      node("span", "dot"),
      document.createTextNode("Reconnecting"),
    );
    connectionLost = true;
    if (last) renderEstimate(last);
  } finally {
    setTimeout(poll, 2000);
  }
}
setInterval(tick, 1000);
$("restart-monitor").addEventListener("click", restartMonitor);
if (dismissedRun) {
  last = waitingForNext({ steps: [] });
  render(last);
}
poll();

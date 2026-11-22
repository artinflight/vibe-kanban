"""Conditional forecasts, separate from measured counters and completion proof.

Range widths are planning assumptions, not statistical confidence intervals.
They neither bound an unknown wait nor authorize an action by the controller.
"""


def forecast(value, now):
    observed = value.get("updated_at")
    if not observed or value.get("status") == "idle":
        return None
    stale = bool(value.get("stale") or value.get("source_error"))
    if value["status"] == "completed":
        return dict(lower_seconds=0, upper_seconds=0, basis="confirmed", confidence="high",
                    confidence_reason="Every planned step has controller completion evidence.",
                    assumptions=[], as_of=observed, stale=stale, conditional=False,
                    recalibration=None)

    lower, upper, bases, assumptions = 0, 0, set(), []
    blocked = value["status"] in {"blocked", "failed"}
    current = next((s for s in value["steps"] if s["id"] == value.get("current_step")), None)
    waiting = blocked or bool(current and current.get("wait_step"))
    for step in value["steps"]:
        if step["status"] in {"completed", "skipped"}:
            continue
        metric = step.get("metric") or {}
        rate = step.get("observed_rate_per_second")
        total, count = metric.get("total"), metric.get("done", 0)
        if step is current and rate and total and total > count:
            seconds = (total - count) / rate
            old = stale or now - metric.get("observed_at", observed) > value.get("stale_after_seconds", 30)
            observed = min(observed, metric.get("observed_at", observed))
            stale = stale or old
            lo, hi = (seconds / 4, seconds * 4) if old or blocked else (seconds / 2, seconds * 2)
            bases.add("rate")
            assumptions.append(f"{step['label']}: extrapolate the last observed {rate:.2g} {metric['unit']}/s; "
                               "assume the remaining total and throughput stay comparable. "
                               + ("The total is approximate. " if metric.get("estimated_total") else "")
                               + ("This observation is stale or work is blocked. " if old or blocked else "")
                               + "The range is a planning band, not a statistical interval.")
        elif step.get("measured_duration_seconds") is not None:
            seconds = step["measured_duration_seconds"]
            lo, hi = seconds / 2, seconds * 2
            bases.add("rehearsal")
            assumptions.append(f"{step['label']}: assume the matching measured rehearsal duration remains representative; "
                               "allow half to twice that duration. This is a forecast, not current measured work.")
        else:
            prior = step.get("planning_estimate", {})
            lo, hi = prior.get("lower_seconds", 120), prior.get("upper_seconds", 600)
            bases.add("planning")
            assumptions.append(f"{step['label']}: planning allowance {lo / 60:g}–{hi / 60:g} min, not measured. "
                               + prior.get("assumption", "Assume this step can proceed normally; no timing evidence is available."))
        lower += lo
        upper += hi

    # A wait for human action/new work has no known upper bound. The numeric
    # range is explicitly conditional on this scenario; never claim it bounds it.
    if blocked and (not current or not current.get("wait_step")):
        lower += 300
        upper += 1800
        bases.add("planning")
        assumptions.insert(0, "Assume the blocker is resolved within 5–30 min, then remaining work proceeds. "
                           "This allowance is not measured and the wait can extend indefinitely; "
                           "a stopped attempt requires controller review and any required authorization.")
    if waiting:
        assumptions.append("The wait can extend indefinitely. Assume no new work extends the idle wait, "
                           "and all existing safety/approval gates pass. "
                           "This scenario does not promise a finish time or trigger a restart.")
    if stale:
        assumptions.append("Observations are stale or unavailable. This is a conditional forecast from the last "
                           "saved state, not confirmation that work is still advancing.")

    low = waiting or stale or "planning" in bases or any(
        (s.get("metric") or {}).get("estimated_total") for s in value["steps"]
        if s["status"] not in {"completed", "skipped"})
    reason = ("Includes unmeasured allowances, approximate totals, a blocker or stale observations."
              if low else "Based on observed throughput or matching rehearsal timings; future work can vary.")
    trigger = (current.get("planning_estimate", {}).get("recalibrate_on") if current else None)
    trigger = trigger or ("Controller review/recovery update or a newly selected authorized attempt"
                          if blocked and value.get("errors")
                          else "Next controller progress observation or stage change")
    # Anchor to evidence, never roll this deadline forward on a poll or reboot.
    due = observed + (60 if waiting or "planning" in bases else value.get("stale_after_seconds", 30))
    return dict(lower_seconds=round(lower), upper_seconds=round(upper),
                basis="planning" if bases == {"planning"} else "mixed" if "planning" in bases else "evidence-based forecast",
                confidence="low" if low else "medium", confidence_reason=reason,
                scope="recovery and remaining restart, if authorized" if blocked and value.get("errors") else "remaining restart",
                assumptions=assumptions, as_of=observed, stale=stale, conditional=True,
                recalibration=dict(trigger=trigger, due_at=due, overdue=now >= due))

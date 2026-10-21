//! Bounded normalization of native structured messages, not prose/exit-code inference.
//! A native observation never grants entitlement, billing, allocation or admission.
use serde::{Deserialize, Serialize};
use serde_json::Value;

use super::*;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Signal {
    pub provider: Provider,
    pub native_session_id: Option<String>,
    pub native_turn_id: Option<String>,
    pub windows: Vec<Window>,
    pub failure: Option<Failure>,
    /// Native retry in progress is not a stopped/checkpointed worker.
    pub native_retrying: Option<bool>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Record {
    pub id: String,
    pub work_id: String,
    pub execution_id: String,
    pub identity: Identity,
    pub source_receipt: String,
    pub observed_at_ms: u64,
    pub signal: Signal,
}
fn text(v: &Value, field: &str) -> io::Result<String> {
    let s = v
        .get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| invalid("Missing native field"))?;
    if !present(s) || s.len() > 200 {
        return Err(invalid("Invalid native field"));
    }
    Ok(s.into())
}
fn unix_ms(v: Option<&Value>) -> io::Result<Option<u64>> {
    match v {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v
            .as_u64()
            .and_then(|n| n.checked_mul(1000))
            .map(Some)
            .ok_or_else(|| invalid("Invalid native reset timestamp")),
    }
}
/// Pinned Codex app-server v2 camelCase protocol. The account event's limitId is
/// bound separately to a trusted account/pool; default is a protocol bucket, NOT
/// an account identity. No window duration or reset timestamp is invented.
pub fn codex(method: &str, params: &Value) -> io::Result<Option<Signal>> {
    if !matches!(method, "account/rateLimits/updated" | "error") {
        return Ok(None);
    }
    let mut s = Signal {
        provider: Provider::Codex,
        native_session_id: None,
        native_turn_id: None,
        windows: vec![],
        failure: None,
        native_retrying: None,
    };
    if method == "error" {
        s.native_session_id = Some(text(params, "threadId")?);
        s.native_turn_id = Some(text(params, "turnId")?);
        s.native_retrying = Some(
            params
                .get("willRetry")
                .and_then(Value::as_bool)
                .ok_or_else(|| invalid("Missing native retry state"))?,
        );
        let error = params.get("error").and_then(|e| e.get("codexErrorInfo"));
        s.failure = Some(match error.and_then(Value::as_str) {
            Some("usageLimitExceeded") => Failure::QuotaUnspecified,
            Some("unauthorized") => Failure::Authentication,
            Some("serverOverloaded" | "internalServerError") => Failure::Outage,
            Some(
                "contextWindowExceeded" | "badRequest" | "threadRollbackFailed" | "sandboxError",
            ) => Failure::TaskFailure,
            _ => {
                let code = error.and_then(Value::as_object).and_then(|o| {
                    [
                        "httpConnectionFailed",
                        "responseStreamConnectionFailed",
                        "responseStreamDisconnected",
                        "responseTooManyFailedAttempts",
                    ]
                    .into_iter()
                    .find_map(|k| o.get(k))
                    .and_then(|v| v.get("httpStatusCode"))
                    .and_then(Value::as_u64)
                });
                match code {
                    Some(401 | 403) => Failure::Authentication,
                    Some(429) => Failure::RateLimit,
                    Some(500..=599) => Failure::Outage,
                    _ => Failure::Unknown,
                }
            }
        });
    } else {
        let r = params
            .get("rateLimits")
            .filter(|v| v.is_object())
            .ok_or_else(|| invalid("Missing native rateLimits"))?;
        let limit = match r.get("limitId") {
            None | Some(Value::Null) => "default".into(),
            Some(_) => text(r, "limitId")?,
        };
        for field in ["primary", "secondary"] {
            let Some(w) = r.get(field).filter(|v| !v.is_null()) else {
                continue;
            };
            let used = w
                .get("usedPercent")
                .and_then(Value::as_u64)
                .ok_or_else(|| invalid("Invalid native utilization"))?;
            let duration = match w.get("windowDurationMins") {
                None | Some(Value::Null) => "unknown_duration".into(),
                Some(v) => format!(
                    "minutes:{}",
                    v.as_u64()
                        .filter(|m| *m > 0)
                        .ok_or_else(|| invalid("Invalid native window duration"))?
                ),
            };
            s.windows.push(Window {
                id: format!("codex:{limit}:{field}"),
                kind: duration,
                available: Some(used < 100),
                reset_at_ms: unix_ms(w.get("resetsAt"))?,
            });
        }
        if s.windows.is_empty() {
            return Err(invalid("No sourced native windows"));
        }
    }
    Ok(Some(s))
}
/// Claude rate_limit_event outer snake_case / rateLimitInfo inner camelCase.
/// Only SDK-documented structured statuses/types are used. Unsupported/missing
/// pinned-CLI fields hold; neither extra-usage entitlement nor API fallback is inferred.
pub fn claude(value: &Value) -> io::Result<Option<Signal>> {
    if value.get("type").and_then(Value::as_str) != Some("rate_limit_event") {
        return Ok(None);
    }
    let session = text(value, "session_id")?;
    let r = value
        .get("rate_limit_info")
        .filter(|v| v.is_object())
        .ok_or_else(|| invalid("Missing Claude rate_limit_info"))?;
    let status = text(r, "status")?;
    let kind = text(r, "rateLimitType")?;
    if !matches!(
        kind.as_str(),
        "five_hour" | "seven_day" | "seven_day_opus" | "seven_day_sonnet" | "overage"
    ) {
        return Err(invalid("Unsupported Claude rate-limit type"));
    }
    let available = match status.as_str() {
        "allowed" | "allowed_warning" => true,
        "rejected" => false,
        _ => return Err(invalid("Unsupported Claude rate-limit status")),
    };
    let id = format!("claude:{kind}");
    Ok(Some(Signal {
        provider: Provider::Claude,
        native_session_id: Some(session),
        native_turn_id: None,
        windows: vec![Window {
            id: id.clone(),
            kind,
            available: Some(available),
            reset_at_ms: unix_ms(r.get("resetsAt"))?,
        }],
        failure: (!available).then_some(Failure::Quota { window_id: id }),
        native_retrying: None,
    }))
}
impl Controller {
    pub(super) fn native_observed(&self, execution: &str) -> bool {
        self.state
            .native_records
            .values()
            .any(|r| r.execution_id == execution)
    }
    /// Host-bound, immutable facts. Native 'allowed' does NOT replace a CU pool
    /// snapshot, complete window inventory, generation, entitlement or billing route.
    pub fn record_native(
        &mut self,
        work_id: &str,
        execution: &str,
        identity: &Identity,
        signal: Signal,
        source_receipt: &str,
        now: u64,
    ) -> io::Result<()> {
        let w = self.work(work_id).ok_or_else(|| invalid("Unknown work"))?;
        let (current, pool_id) = match &w.phase {
            Phase::Watching => (&w.execution_id, &w.incumbent.pool_id),
            Phase::DispatchPending(t) | Phase::Running(t) => {
                (&t.execution_id, &t.candidate.pool_id)
            }
            Phase::Finished(_) => return Err(invalid("Finished work")),
        };
        let p = self
            .state
            .pools
            .get(pool_id)
            .ok_or_else(|| invalid("Unknown pool"))?;
        if current != execution
            || &p.identity != identity
            || signal.provider != identity.provider
            || identity.provider == Provider::Antigravity
            || !present(source_receipt)
            || source_receipt.len() > 500
            || now < self.state.last_now_ms
            || signal.windows.len() > 32
        {
            return Err(invalid("Unbound native observation"));
        }
        let normalized = serde_json::to_string(&signal)?;
        if normalized.len() > 8192 {
            return Err(invalid("Native observation too large"));
        }
        // Normalized, bounded protocol facts, never private raw messages. A duplicate
        // received later cannot extend cooldown or alter an immutable event's time.
        let id = format!("native:{execution}:{normalized}");
        if self.state.native_records.contains_key(&id) {
            return Ok(());
        }
        let mut next = self.state.clone();
        let record = Record {
            id: id.clone(),
            work_id: work_id.into(),
            execution_id: execution.into(),
            identity: identity.clone(),
            source_receipt: source_receipt.into(),
            observed_at_ms: now,
            signal: signal.clone(),
        };
        let mut failures = vec![];
        if let Some(failure) = signal.failure {
            failures.push(failure);
        }
        for window in &signal.windows {
            if window.available == Some(false)
                && !failures.contains(&Failure::Quota {
                    window_id: window.id.clone(),
                })
            {
                failures.push(Failure::Quota {
                    window_id: window.id.clone(),
                });
            }
        }
        for (index, mut failure) in failures.into_iter().enumerate() {
            let mut until = now;
            if let Failure::Quota { window_id } = &failure {
                // A native bucket not in the authoritative inventory must still block
                // this pool, but cannot be relabelled as an already verified bucket.
                if let Some(window) = p.windows.iter().find(|w| &w.id == window_id) {
                    until = until.max(window.reset_at_ms.unwrap_or(now));
                } else {
                    failure = Failure::QuotaUnspecified;
                }
            }
            until = until.max(
                signal
                    .windows
                    .iter()
                    .filter(|w| w.available == Some(false))
                    .filter_map(|w| w.reset_at_ms)
                    .max()
                    .unwrap_or(now),
            );
            if matches!(
                failure,
                Failure::RateLimit | Failure::Outage | Failure::Authentication
            ) {
                until = until.max(now.saturating_add(60_000));
            }
            let event = LimitEvent {
                id: format!("{id}:{index}"),
                execution_id: execution.into(),
                identity: identity.clone(),
                source_receipt: source_receipt.into(),
                observed_at_ms: now,
                failure,
                retry_at_ms: Some(until),
            };
            if !matches!(event.failure, Failure::TaskFailure | Failure::Unknown) {
                next.blocks.entry(pool_id.clone()).or_default().push(Block {
                    event: event.clone(),
                    generation: p.generation.clone(),
                    until_ms: until,
                });
            }
            next.events.insert(event.id.clone(), event.clone());
            next.works.get_mut(work_id).unwrap().event = Some(event);
        }
        next.last_now_ms = now;
        next.native_records.insert(id, record);
        self.commit(next)
    }
}

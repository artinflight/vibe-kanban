//! Concrete, read-only adapters for sealed Git readiness and pinned CU observations.
//! They NEVER create quota/permission/budget grants, leases, successful checkpoints,
//! missing native captures or a provider process. CU is the local service only.
use std::{process::Stdio, time::Duration};

use db::models::execution_process::ExecutionProcess;
use executors::provider_failover::{self as pf, readiness::Readiness};
use serde_json::{Value, json};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    process::Command,
};
use uuid::Uuid;

use super::container::{ContainerError, ContainerService};
const CU_READER: &str = include_str!("../../../../scripts/routing/provider_receipts.py");
const MAX_OUTPUT: u64 = 128 * 1024;
fn blocked(workspace: Uuid, execution: Uuid, code: &str, action: &str) -> ContainerError {
    ContainerError::ReadinessBlocked(json!({"version":2,"state":"blocked","workspace":workspace,
        "turn":execution,"code":code,"action":action,"provider_started":false,"coverage_verified":false}))
}
fn disposition(code: &str, action: &str) -> Readiness {
    Readiness::Blocked {
        code: code.into(),
        action: action.into(),
        provider_started: false,
    }
}
/// Tiny embedded helper follows the existing Git helper's isolated one-shot pattern.
/// Stdout is a bounded metadata projection, stderr is not exposed. No env credentials,
/// proxy settings, arbitrary URLs, retries, external provider calls or dependencies.
pub async fn cu(
    provider: pf::Provider,
    pool: Option<&str>,
    binding_receipt: Option<&str>,
    model: Option<&str>,
) -> Result<Value, ()> {
    let name = match provider {
        pf::Provider::Codex => "codex",
        pf::Provider::Claude => "claude",
        _ => return Err(()),
    };
    let request = serde_json::to_vec(
        &json!({"provider":name,"poolId":pool,"bindingReceipt":binding_receipt,"model":model}),
    )
    .map_err(|_| ())?;
    let work = async {
        let mut child = Command::new("python3")
            .arg("-I")
            .arg("-B")
            .arg("-c")
            .arg(CU_READER)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .kill_on_drop(true)
            .spawn()
            .map_err(|_| ())?;
        let mut input = child.stdin.take().ok_or(())?;
        input.write_all(&request).await.map_err(|_| ())?;
        drop(input);
        let mut bytes = Vec::new();
        child
            .stdout
            .take()
            .ok_or(())?
            .take(MAX_OUTPUT + 1)
            .read_to_end(&mut bytes)
            .await
            .map_err(|_| ())?;
        if bytes.len() as u64 > MAX_OUTPUT {
            return Err(());
        }
        if !child.wait().await.map_err(|_| ())?.success() {
            return Err(());
        }
        let report: Value = serde_json::from_slice(&bytes).map_err(|_| ())?;
        if report["contractVersion"] != "vk.cu-observation.v1"
            || report["dispatchAuthority"] != false
            || report["providerStarted"] != false
        {
            return Err(());
        }
        Ok(report)
    };
    tokio::time::timeout(Duration::from_secs(8), work)
        .await
        .map_err(|_| ())?
}
/// Consume Git's EXACT result shape, never calling a pending receipt preservation
/// proof. Its private admission_request is retained in-process for exact recheck.
pub async fn git<C: ContainerService + ?Sized>(
    container: &C,
    execution: Uuid,
    context: Value,
    reusable: bool,
) -> Result<Value, ContainerError> {
    let ctx = ExecutionProcess::load_context(&container.db().pool, execution).await?;
    let report = container
        .execution_git_readiness(&ctx.workspace, &ctx.execution_process, context)
        .await?;
    validate_git(
        &report,
        ctx.workspace.id,
        execution,
        reusable,
        chrono::Utc::now().timestamp_millis(),
    )?;
    Ok(report)
}
pub fn validate_git(
    result: &Value,
    workspace: Uuid,
    execution: Uuid,
    reusable: bool,
    now_ms: i64,
) -> Result<(), ContainerError> {
    let r = &result["receipt"];
    let good = r["version"] == 2
        && r["readiness_version"] == 1
        && r["inventory_version"] == 1
        && r["state"] == "pending"
        && r["code"] == "git_ready"
        && r["provider_started"] == false
        && r["coverage_verified"] == false
        && r["provider_availability_checked"] == false
        && r["scope"] == "git_ownership_only"
        && r["workspace"].as_str() == Some(workspace.to_string().as_str())
        && r["turn"].as_str() == Some(execution.to_string().as_str())
        && (!reusable || r["reusable"] == true)
        && result["admission_request"].is_object();
    let times = r["issued_at"].as_f64().zip(r["valid_until"].as_f64());
    let valid = times.is_some_and(|(a, b)| {
        a.is_finite()
            && b.is_finite()
            && a * 1000.0 <= now_ms as f64
            && (now_ms as f64) < b * 1000.0
            && b > a
            && b - a <= 30.0
    });
    if !good || !valid {
        return Err(blocked(
            workspace,
            execution,
            "readiness_stale_or_invalid",
            "refresh_exact_git_owner_receipt",
        ));
    }
    Ok(())
}
/// Default host preparation is no longer a generic missing-adapter placeholder:
/// read the actual persisted owner, actual Git gate and actual CU contract. It
/// returns precise producer gaps without constructing a Work/Admission from tokens.
pub async fn preparation<C: ContainerService + ?Sized>(
    container: &C,
    execution: Uuid,
) -> Readiness {
    // Probe Git ownership/policy first, without pretending trusted permissions or
    // toolchain evidence exist. A nonreusable probe is never used to launch.
    if let Err(error) = git(container, execution, json!({}), false).await {
        return match error {
            ContainerError::ReadinessBlocked(r) => disposition(
                r["code"].as_str().unwrap_or("git_admission_blocked"),
                r["action"]
                    .as_str()
                    .unwrap_or("review_exact_admission_failure"),
            ),
            _ => disposition("readiness_query_failed", "retry_exact_read_only_checkpoint"),
        };
    }
    // Native Claude consideration is a separate entitlement; no account identity
    // is invented from the selected Sol model or a successful old Claude trial.
    let observation = match cu(pf::Provider::Claude, None, None, None).await {
        Ok(r) => r,
        Err(_) => {
            return disposition(
                "cu_observation_unavailable",
                "inspect_existing_cu_observation_service",
            );
        }
    };
    if let Some(reason) = observation["blockers"].as_array().and_then(|a| a.first()) {
        return disposition(
            reason["code"].as_str().unwrap_or("cu_quota_unknown"),
            reason["action"]
                .as_str()
                .unwrap_or("await_bound_provider_metadata"),
        );
    }
    disposition(
        "task_scoped_admission_receipt_required",
        "obtain_real_bound_quota_and_existing_admission_permit",
    )
}
/// Completion must not depend on having enough quota for ANOTHER turn. Check
/// the actual Git owner, then require the independent accepted-result producer.
pub async fn completion_preparation<C: ContainerService + ?Sized>(
    container: &C,
    execution: Uuid,
) -> Readiness {
    if let Err(error) = git(container, execution, json!({}), false).await {
        return match error {
            ContainerError::ReadinessBlocked(r) => disposition(
                r["code"].as_str().unwrap_or("git_admission_blocked"),
                r["action"]
                    .as_str()
                    .unwrap_or("review_exact_admission_failure"),
            ),
            _ => disposition("readiness_query_failed", "retry_exact_read_only_checkpoint"),
        };
    }
    disposition(
        "accepted_result_receipt_required",
        "verify_task_result_without_new_provider_turn",
    )
}
/// CU corroborates metadata only. The caller still validates Controller Pool,
/// complete native window inventory/generation and the independent existing permit.
pub fn require_cu(report: &Value, workspace: Uuid, execution: Uuid) -> Result<(), ContainerError> {
    if report["contractVersion"] != "vk.cu-observation.v1"
        || report["dispatchAuthority"] != false
        || report["providerStarted"] != false
        || !report["blockers"].is_array()
    {
        return Err(blocked(
            workspace,
            execution,
            "cu_observation_invalid",
            "inspect_existing_cu_observation_service",
        ));
    }
    if let Some(reason) = report["blockers"].as_array().and_then(|a| a.first()) {
        return Err(blocked(
            workspace,
            execution,
            reason["code"].as_str().unwrap_or("cu_quota_unknown"),
            reason["action"]
                .as_str()
                .unwrap_or("await_fresh_provider_quota_evidence"),
        ));
    }
    let time = chrono::Utc::now().timestamp_millis();
    if time < 0
        || report["quotaExpiresAtMs"]
            .as_u64()
            .is_none_or(|t| t <= time as u64)
    {
        return Err(blocked(
            workspace,
            execution,
            "cu_observation_stale",
            "await_fresh_provider_quota_evidence",
        ));
    }
    if report["status"] != "observed"
        || report["bindingMatched"] != true
        || report["quotaState"] != "observed-available"
    {
        return Err(blocked(
            workspace,
            execution,
            "cu_quota_unknown",
            "await_fresh_bound_provider_quota_evidence",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture(ws: Uuid, execution: Uuid, now: i64) -> Value {
        json!({"receipt":{"version":2,"readiness_version":1,"inventory_version":1,
            "state":"pending","code":"git_ready","provider_started":false,"coverage_verified":false,
            "provider_availability_checked":false,"scope":"git_ownership_only","workspace":ws,"turn":execution,
            "issued_at":now as f64/1000.0-1.0,"valid_until":now as f64/1000.0+29.0,"reusable":true},"admission_request":{}})
    }
    #[test]
    fn git_only_success_is_not_preservation_or_quota_and_binding_is_exact() {
        let ws = Uuid::new_v4();
        let execution = Uuid::new_v4();
        let now = 1_792_608_000_000;
        let value = fixture(ws, execution, now);
        validate_git(&value, ws, execution, true, now).unwrap();
        assert!(validate_git(&value, ws, Uuid::new_v4(), true, now).is_err());
        assert!(validate_git(&value, Uuid::new_v4(), execution, true, now).is_err());
        let mut wrong = value.clone();
        wrong["receipt"]["coverage_verified"] = json!(true);
        assert!(validate_git(&wrong, ws, execution, true, now).is_err());
        let mut probe = value;
        probe["receipt"]["reusable"] = json!(false);
        assert!(validate_git(&probe, ws, execution, true, now).is_err());
    }
    #[test]
    fn git_ttl_expiry_future_or_missing_fields_never_spawn() {
        let ws = Uuid::new_v4();
        let e = Uuid::new_v4();
        let now = 1_792_608_000_000;
        let v = fixture(ws, e, now);
        assert!(validate_git(&v, ws, e, true, now + 29_000).is_err());
        assert!(validate_git(&v, ws, e, true, now - 1_001).is_err());
        let mut long = v.clone();
        long["receipt"]["valid_until"] = json!(now as f64 / 1000.0 + 30.0);
        assert!(validate_git(&long, ws, e, true, now).is_err());
        let mut missing = v;
        missing["receipt"]
            .as_object_mut()
            .unwrap()
            .remove("provider_started");
        assert!(validate_git(&missing, ws, e, true, now).is_err());
    }
    #[test]
    fn cu_precise_gap_is_not_hidden_by_absent_expiry_or_reporting_false_flag() {
        let ws = Uuid::new_v4();
        let e = Uuid::new_v4();
        let v = json!({"contractVersion":"vk.cu-observation.v1","dispatchAuthority":false,"providerStarted":false,
            "quotaExpiresAtMs":null,"blockers":[{"code":"cu_account_pool_binding_unknown","action":"verify_native_account_pool_binding"}]});
        let Err(ContainerError::ReadinessBlocked(report)) = require_cu(&v, ws, e) else {
            panic!("expected block")
        };
        assert_eq!(report["code"], "cu_account_pool_binding_unknown");
        assert_eq!(report["provider_started"], false);
    }
}

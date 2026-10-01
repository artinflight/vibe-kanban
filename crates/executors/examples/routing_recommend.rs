//! Admission recommendations; semantic inference requires explicit --semantic.
//! Input: one JSON object per line with prompt and optional previous_envelope/floor/
//! denied_models. Default is zero inference. --semantic explicitly allows one bounded
//! classifier call per uncertain request, with usage telemetry; never implements work.
use std::io::{self, BufRead};

use executors::{
    routing::{
        CapabilityFloor, RoutingMode, RoutingPolicy, choose_assessed, load_availability,
        model_policies,
    },
    routing_assessment::{assess_with_context, retain_previous},
    routing_semantic,
};
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Task {
    prompt: String,
    previous_envelope: Option<String>,
    repo_root: Option<std::path::PathBuf>,
    #[serde(default)]
    floor: CapabilityFloor,
    #[serde(default)]
    denied_models: Vec<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let semantic_enabled = std::env::args().any(|arg| arg == "--semantic");
    let models = model_policies().map_err(io::Error::other)?;
    let availability = load_availability();
    for line in io::stdin().lock().lines() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let task: Task = serde_json::from_str(&line)?;
        let mut assessment = assess_with_context(&task.prompt, task.repo_root.as_deref());
        let mut policy = RoutingPolicy {
            mode: RoutingMode::Auto,
            floor: task.floor,
            denied_models: task.denied_models,
            allow_escalation: false,
        };
        let semantic = if semantic_enabled
            && routing_semantic::eligible(
                &assessment,
                false,
                &policy,
                &task.prompt,
                task.previous_envelope.as_deref(),
            ) {
            let trace = routing_semantic::classify(&task.prompt, None, &assessment, &policy);
            if let Some(c) = &trace.classification {
                routing_semantic::apply(&mut assessment, c);
            }
            Some(trace)
        } else {
            None
        };
        let assessment =
            retain_previous(assessment, &task.prompt, task.previous_envelope.as_deref());
        let floor = task.floor.max(assessment.floor);
        policy.floor = floor;
        // This tool evaluates initial admission only; failure escalation needs the
        // persisted prior action/status and must go through VK's boundary resolver.
        let recommendation = |policy: &RoutingPolicy| {
            if assessment.validation_failure {
                return Err(
                    "Failure escalation requires VK's persisted execution context".to_owned(),
                );
            }
            availability
                .as_ref()
                .map_err(Clone::clone)
                .and_then(|proof| {
                    choose_assessed(
                        policy,
                        floor,
                        assessment.envelope,
                        &models,
                        proof,
                        chrono::Utc::now().timestamp(),
                    )
                })
        };
        let auto = recommendation(&policy);
        policy.mode = RoutingMode::Shadow;
        let shadow = recommendation(&policy);
        println!(
            "{}",
            json!({
                "kind": "offline_recommendation", "envelope": assessment.envelope,
                "semantic": semantic, "prompt": task.prompt,
                "minimum": floor, "evidence": assessment.evidence, "triage": assessment.triage,
                "requires_failure_review": assessment.validation_failure,
                "auto_candidate": auto.as_ref().ok(), "auto_blocker": auto.as_ref().err(),
                "shadow_candidate": shadow.as_ref().ok(), "shadow_blocker": shadow.as_ref().err(),
                "service_tier": "standard"
            })
        );
    }
    Ok(())
}

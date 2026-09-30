//! Opt-in routing at persisted VK execution boundaries. No scheduler or retry loop.
use serde::{Deserialize, Serialize};
use ts_rs::TS;

use crate::{
    actions::{ExecutorAction, ExecutorActionType},
    executors::{BaseCodingAgent, CodingAgent, codex::Codex},
    profile::{ExecutorConfig, ExecutorConfigs},
};

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize, TS)]
#[serde(rename_all = "snake_case")]
pub enum RoutingMode {
    #[default]
    Manual,
    Shadow,
    Auto,
}

#[derive(
    Debug, Clone, Copy, Default, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize, TS,
)]
#[serde(rename_all = "snake_case")]
pub enum CapabilityFloor {
    #[default]
    Assessed,
    Routine,
    Workhorse,
    Frontier,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, TS)]
#[serde(deny_unknown_fields)]
pub struct RoutingPolicy {
    pub mode: RoutingMode,
    #[serde(default)]
    pub floor: CapabilityFloor,
    #[serde(default)]
    pub denied_models: Vec<String>,
    /// Consent to escalate on a failed execution at the next explicit follow-up.
    #[serde(default)]
    pub allow_escalation: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, TS)]
pub struct RoutingDecision {
    pub version: u32,
    pub id: String,
    pub mode: RoutingMode,
    pub floor: CapabilityFloor,
    pub reason: String,
    /// Persist qualification context independently of human-readable reasons.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub assessed_envelope: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub triage: Option<crate::routing_triage::TaskTriage>,
    pub requested_model: Option<String>,
    pub selected_model: Option<String>,
    pub selected_effort: Option<String>,
    pub service_tier: String,
    pub previous_model: Option<String>,
    pub previous_execution_id: Option<String>,
    pub escalated: bool,
    #[ts(type = "number | null")]
    pub catalog_observed_at: Option<i64>,
    pub account_fingerprint: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Qualification {
    pub effort: String,
    pub envelope: String,
    pub status: QualificationStatus,
    pub floor: CapabilityFloor,
    pub preference_rank: u32,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QualificationStatus {
    Qualified,
    Experimental,
    Denied,
    MinimumRequired,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelPolicy {
    pub id: String,
    pub released: bool,
    pub efforts: Vec<String>,
    pub floor: CapabilityFloor,
    /// Operator-adjustable preference, not a claimed Codex allowance multiplier.
    pub cost_rank: u32,
    #[serde(default)]
    pub qualifications: Vec<Qualification>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Availability {
    pub version: u32,
    pub observed_at: i64,
    pub codex_home: String,
    pub launcher: String,
    pub account_fingerprint: String,
    pub models: Vec<ModelAvailability>,
}
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelAvailability {
    pub id: String,
    pub discovered: bool,
    pub supported_efforts: Vec<String>,
    pub verified_efforts: Vec<String>,
    pub verified_at: Option<i64>,
}

pub fn model_policies() -> Result<Vec<ModelPolicy>, String> {
    let json = match std::env::var("VK_CODEX_ROUTING_MODELS") {
        Ok(path) => std::fs::read_to_string(path).map_err(|e| e.to_string())?,
        Err(_) => include_str!("routing_models.json").to_owned(),
    };
    let models: Vec<ModelPolicy> = serde_json::from_str(&json).map_err(|e| e.to_string())?;
    let mut ids = std::collections::HashSet::new();
    if models.is_empty() || models.iter().any(|m| m.id.is_empty() || !ids.insert(&m.id)) {
        return Err("Routing model policies must have unique nonempty IDs".into());
    }
    for model in &models {
        let mut pairs = std::collections::HashSet::new();
        for q in &model.qualifications {
            if !model.efforts.contains(&q.effort)
                || !["low", "medium", "high", "xhigh", "max"].contains(&q.effort.as_str())
                || ![
                    "mechanical",
                    "bounded",
                    "validated_fix",
                    "normal",
                    "complex",
                    "protected",
                ]
                .contains(&q.envelope.as_str())
                || q.floor == CapabilityFloor::Assessed
                || !pairs.insert((&q.effort, &q.envelope))
            {
                return Err("Invalid or duplicate model/effort/envelope qualification".into());
            }
        }
    }
    Ok(models)
}

pub fn load_availability() -> Result<Availability, String> {
    let path = std::env::var("VK_CODEX_ROUTING_AVAILABILITY").map_err(
        |_| "Routing requires VK_CODEX_ROUTING_AVAILABILITY; run the catalog probe first",
    )?;
    let data = std::fs::read_to_string(path).map_err(|e| e.to_string())?;
    let a: Availability = serde_json::from_str(&data).map_err(|e| e.to_string())?;
    let home = crate::executors::codex::codex_home()
        .and_then(|p| p.canonicalize().ok())
        .ok_or("Codex home unavailable")?;
    let age = chrono::Utc::now().timestamp() - a.observed_at;
    if a.version != 1
        || !(0..=86400).contains(&age)
        || a.codex_home != home.to_string_lossy()
        || a.launcher != Codex::base_command()
        || a.account_fingerprint.is_empty()
    {
        return Err(
            "Routing availability is stale or belongs to another runtime; refresh the probe".into(),
        );
    }
    Ok(a)
}

pub fn config(action: &ExecutorAction) -> Option<&ExecutorConfig> {
    match &action.typ {
        ExecutorActionType::CodingAgentInitialRequest(r) => Some(&r.executor_config),
        ExecutorActionType::CodingAgentFollowUpRequest(r) => Some(&r.executor_config),
        ExecutorActionType::ReviewRequest(r) => Some(&r.executor_config),
        _ => None,
    }
}

/// Resolve a cloned action before it is stored. Never touches files, Git or profiles.
pub fn resolve_action(
    action: &mut ExecutorAction,
    previous: Option<&ExecutorAction>,
    failed: bool,
) -> Result<(), String> {
    resolve_action_with_context(action, previous, failed, None)
}

pub fn resolve_action_with_context(
    action: &mut ExecutorAction,
    previous: Option<&ExecutorAction>,
    failed: bool,
    root: Option<&std::path::Path>,
) -> Result<(), String> {
    let original = action.clone();
    let shadow = config(action)
        .and_then(|c| c.routing.as_ref())
        .is_some_and(|p| p.mode == RoutingMode::Shadow);
    let result = resolve_action_inner(action, previous, failed, root);
    if shadow {
        action.typ = original.typ;
        if let Err(error) = result {
            let c = config(action).expect("shadow policy has config");
            action.routing_decision = Some(Box::new(RoutingDecision {
                assessed_envelope: None,
                triage: None,
                version: 2,
                id: uuid::Uuid::new_v4().to_string(),
                mode: RoutingMode::Shadow,
                floor: c.routing.as_ref().unwrap().floor,
                reason: format!("recommendation_unavailable: {error}"),
                requested_model: c.model_id.clone(),
                selected_model: None,
                selected_effort: None,
                service_tier: "standard".into(),
                previous_model: previous.and_then(config).and_then(|c| c.model_id.clone()),
                previous_execution_id: None,
                escalated: false,
                catalog_observed_at: None,
                account_fingerprint: None,
            }));
        }
        return Ok(());
    }
    result
}

fn resolve_action_inner(
    action: &mut ExecutorAction,
    previous: Option<&ExecutorAction>,
    failed: bool,
    root: Option<&std::path::Path>,
) -> Result<(), String> {
    action.routing_decision = None; // Never trust a client-supplied decision.
    let Some(original) = config(action).cloned() else {
        return Ok(());
    };
    if original.executor != BaseCodingAgent::Codex {
        return Ok(());
    }
    let policy = original
        .routing
        .as_deref()
        .cloned()
        .unwrap_or(RoutingPolicy {
            mode: RoutingMode::Manual,
            floor: CapabilityFloor::Workhorse,
            denied_models: vec![],
            allow_escalation: false,
        });
    if policy.mode == RoutingMode::Manual {
        return Ok(());
    }
    let (prompt, pinned) = match &action.typ {
        ExecutorActionType::CodingAgentInitialRequest(r) => (r.prompt.as_str(), false),
        ExecutorActionType::CodingAgentFollowUpRequest(r) => (
            r.prompt.as_str(),
            r.capacity.is_some() || r.prompt.trim_start().starts_with('/'),
        ),
        _ => {
            return Err(
                "Automatic routing is not enabled for review actions; choose a manual model".into(),
            );
        }
    };
    // Native controls/resumes retain the already-resolved execution settings.
    if pinned && policy.mode == RoutingMode::Shadow {
        return Ok(());
    }
    if pinned {
        if failed {
            return Err("Failed native execution requires diagnosis and an ordinary follow-up or explicit manual selection".into());
        }
        let prior_decision = previous.and_then(|p| p.routing_decision.as_ref())
            .filter(|d| d.mode == RoutingMode::Auto)
            .ok_or("Native resume cannot enable automatic routing; select manual or use an ordinary follow-up first")?;
        let prior = previous
            .and_then(config)
            .ok_or("A native resume requires an existing execution configuration")?;
        let model = prior
            .model_id
            .as_deref()
            .ok_or("Choose an explicit model before an automatic native resume")?;
        let base_model = model.trim_end_matches("-fast");
        let models = model_policies()?;
        if policy.denied_models.iter().any(|id| id == base_model)
            || !models.iter().any(|m| {
                m.id == base_model
                    && m.qualifications.iter().any(|q| {
                        Some(q.effort.as_str()) == prior.reasoning_id.as_deref()
                            && q.floor >= policy.floor
                            && matches!(
                                q.status,
                                QualificationStatus::Qualified
                                    | QualificationStatus::MinimumRequired
                            )
                    })
            })
        {
            return Err("Pinned native model conflicts with the current floor/exclusions; choose a manual model at a safe boundary".into());
        }
        if let ExecutorActionType::CodingAgentFollowUpRequest(r) = &mut action.typ {
            r.executor_config.model_id = prior.model_id.clone();
            r.executor_config.reasoning_id = prior.reasoning_id.clone();
        }
        let mut decision = prior_decision.clone();
        decision.id = uuid::Uuid::new_v4().to_string();
        decision.reason = "native_resume_pinned".into();
        decision.floor = decision.floor.max(policy.floor);
        decision.requested_model = original.model_id;
        decision.previous_model = prior.model_id.clone();
        decision.escalated = false;
        action.routing_decision = Some(decision);
        return Ok(());
    }
    let prior_envelope = previous.and_then(|p| {
        p.routing_decision
            .as_ref()
            .and_then(|d| d.assessed_envelope.clone())
            .or_else(|| match &p.typ {
                ExecutorActionType::CodingAgentInitialRequest(r) => Some(
                    crate::routing_assessment::assess(&r.prompt)
                        .envelope
                        .to_owned(),
                ),
                ExecutorActionType::CodingAgentFollowUpRequest(r) => Some(
                    crate::routing_assessment::assess(&r.prompt)
                        .envelope
                        .to_owned(),
                ),
                _ => None,
            })
    });
    let assessment = crate::routing_assessment::assess_follow_up_with_context(
        prompt,
        prior_envelope.as_deref(),
        root,
    );
    let mut floor = policy.floor.max(assessment.floor);
    if let Some(prior) = previous.and_then(|p| p.routing_decision.as_ref()) {
        floor = floor.max(prior.floor); // Never silently lower an established session floor.
    }
    let risk_expansion = previous
        .and_then(|p| p.routing_decision.as_ref())
        .is_some_and(|d| assessment.floor > d.floor);
    if risk_expansion && !policy.allow_escalation && policy.mode == RoutingMode::Auto {
        return Err("Task scope exceeds the established capability; allow boundary escalation or select a manual model".into());
    }
    let reported_failure = previous.is_some() && assessment.validation_failure;
    let failed = failed || reported_failure;
    let mut reason = format!("assessed_{}: {}", assessment.envelope, assessment.evidence);
    let escalated = failed || risk_expansion;
    if risk_expansion {
        reason = format!(
            "risk_expansion_{}: {}",
            assessment.envelope, assessment.evidence
        );
    }
    if failed {
        let mut failed_floor = previous
            .and_then(|p| p.routing_decision.as_ref())
            .map(|d| d.floor)
            .unwrap_or(policy.floor.max(CapabilityFloor::Routine));
        // A failed manual model is not evidence that a lower auto tier is safe.
        if let Some(prior_model) = previous
            .and_then(config)
            .and_then(|c| c.model_id.as_deref())
        {
            let models = model_policies()?;
            let prior = models
                .iter()
                .find(|m| m.id == prior_model.trim_end_matches("-fast"))
                .ok_or("Failed model has no known capability policy; manual diagnosis required")?;
            failed_floor = failed_floor.max(prior.floor);
        }
        if !policy.allow_escalation && policy.mode == RoutingMode::Auto {
            return Err("Previous execution failed. Inspect the failure, then choose a manual model or allow boundary escalation".into());
        }
        let raised = match failed_floor {
            CapabilityFloor::Assessed | CapabilityFloor::Routine => CapabilityFloor::Workhorse,
            CapabilityFloor::Workhorse => CapabilityFloor::Frontier,
            CapabilityFloor::Frontier if policy.mode == RoutingMode::Auto => {
                return Err("Frontier execution failed; manual diagnosis required".into());
            }
            CapabilityFloor::Frontier => CapabilityFloor::Frontier,
        };
        floor = floor.max(raised);
        reason = if reported_failure {
            "operator_reported_validation_failure"
        } else {
            "previous_execution_failed"
        }
        .into();
    }
    let envelope = if failed {
        if floor == CapabilityFloor::Frontier {
            "protected"
        } else {
            "normal"
        }
    } else {
        assessment.envelope
    };
    let result = load_availability().and_then(|availability| {
        let models = model_policies()?;
        let chosen = choose_assessed(
            &policy,
            floor,
            envelope,
            &models,
            &availability,
            chrono::Utc::now().timestamp(),
        )?;
        Ok((chosen, availability))
    });
    let mut decision = RoutingDecision {
        assessed_envelope: Some(envelope.into()),
        triage: Some(assessment.triage),
        version: 2,
        id: uuid::Uuid::new_v4().to_string(),
        mode: policy.mode,
        floor,
        reason,
        requested_model: original.model_id.clone(),
        selected_model: None,
        selected_effort: None,
        service_tier: "standard".into(),
        previous_model: previous.and_then(config).and_then(|c| c.model_id.clone()),
        previous_execution_id: None,
        escalated,
        catalog_observed_at: None,
        account_fingerprint: None,
    };
    match result {
        Ok(((model, effort), availability)) => {
            decision.selected_model = Some(model.clone());
            decision.selected_effort = Some(effort.clone());
            decision.catalog_observed_at = Some(availability.observed_at);
            decision.account_fingerprint = Some(availability.account_fingerprint);
            if policy.mode == RoutingMode::Auto {
                let CodingAgent::Codex(codex) = ExecutorConfigs::get_cached()
                    .get_coding_agent(&original.profile_id())
                    .ok_or("Missing Codex profile")?
                else {
                    return Err("Codex profile required".into());
                };
                // Catalog proof must refer to the same launcher/provider; fail closed on unbound overrides.
                if codex.profile.is_some()
                    || codex.model_provider.is_some()
                    || codex.oss == Some(true)
                    || codex.cmd != crate::command::CmdOverrides::default()
                {
                    return Err("Automatic routing requires the verified default Codex launcher/provider (no profile command overrides)".into());
                }
                let c = match &mut action.typ {
                    ExecutorActionType::CodingAgentInitialRequest(r) => &mut r.executor_config,
                    ExecutorActionType::CodingAgentFollowUpRequest(r) => &mut r.executor_config,
                    _ => unreachable!(),
                };
                c.model_id = Some(model);
                c.reasoning_id = Some(effort);
            }
        }
        Err(error) if policy.mode == RoutingMode::Shadow => {
            decision.reason = format!("recommendation_unavailable: {error}")
        }
        Err(error) => return Err(error),
    }
    action.routing_decision = Some(Box::new(decision));
    Ok(())
}

pub fn choose(
    policy: &RoutingPolicy,
    floor: CapabilityFloor,
    models: &[ModelPolicy],
    availability: &Availability,
    now: i64,
) -> Result<(String, String), String> {
    choose_assessed(
        policy,
        floor,
        match floor {
            CapabilityFloor::Assessed | CapabilityFloor::Routine => "bounded",
            CapabilityFloor::Workhorse => "normal",
            CapabilityFloor::Frontier => "protected",
        },
        models,
        availability,
        now,
    )
}

pub fn choose_assessed(
    policy: &RoutingPolicy,
    floor: CapabilityFloor,
    envelope: &str,
    models: &[ModelPolicy],
    availability: &Availability,
    now: i64,
) -> Result<(String, String), String> {
    let mut eligible = Vec::new();
    // Minimum-required rows form a configurable protected-work allowlist.
    let protected = models.iter().any(|m| {
        m.qualifications
            .iter()
            .any(|q| q.envelope == envelope && q.status == QualificationStatus::MinimumRequired)
    });
    for model in models
        .iter()
        .filter(|m| m.released && !policy.denied_models.contains(&m.id))
    {
        let Some(proof) = availability.models.iter().find(|a| {
            a.id == model.id
                && a.verified_at
                    .is_some_and(|at| (0..=86400).contains(&(now - at)))
        }) else {
            continue;
        };
        for q in &model.qualifications {
            if q.envelope != envelope
                || q.floor < floor
                || q.status == QualificationStatus::Denied
                || (q.status == QualificationStatus::Experimental
                    && policy.mode != RoutingMode::Shadow)
                || (protected && q.status != QualificationStatus::MinimumRequired)
            {
                continue;
            }
            if model.efforts.contains(&q.effort)
                && proof.verified_efforts.contains(&q.effort)
                && (!proof.discovered || proof.supported_efforts.contains(&q.effort))
            {
                eligible.push((q.preference_rank, model.id.clone(), q.effort.clone()));
            }
        }
    }
    eligible.sort();
    eligible.into_iter().next().map(|(_, model, effort)| (model, effort))
        .ok_or_else(|| "No verified qualified model/effort meets the assessed envelope, safety floor and exclusions; manual diagnosis or policy qualification required".into())
}

pub fn account_fingerprint(account: &serde_json::Value) -> String {
    use sha2::{Digest, Sha256};
    let identity = format!(
        "{}:{}",
        account["type"].as_str().unwrap_or_default(),
        account["email"].as_str().unwrap_or_default()
    );
    format!("{:x}", Sha256::digest(identity.as_bytes()))
}

#[cfg(test)]
mod tests {
    use super::*;
    fn fixture() -> (RoutingPolicy, Vec<ModelPolicy>, Availability) {
        let policy = RoutingPolicy {
            mode: RoutingMode::Auto,
            floor: CapabilityFloor::Workhorse,
            denied_models: vec![],
            allow_escalation: false,
        };
        let models: Vec<ModelPolicy> =
            serde_json::from_str(include_str!("routing_models.json")).unwrap();
        let availability = Availability {
            version: 1,
            observed_at: 100,
            codex_home: "test".into(),
            launcher: "codex".into(),
            account_fingerprint: "test".into(),
            models: models
                .iter()
                .map(|m| ModelAvailability {
                    id: m.id.clone(),
                    discovered: true,
                    supported_efforts: vec!["medium".into(), "high".into()],
                    verified_efforts: vec!["medium".into(), "high".into()],
                    verified_at: Some(100),
                })
                .collect(),
        };
        (policy, models, availability)
    }
    fn action(policy: Option<RoutingPolicy>) -> ExecutorAction {
        let mut config = ExecutorConfig::new(BaseCodingAgent::Codex);
        config.model_id = Some("gpt-6-astra".into());
        config.reasoning_id = Some("high".into());
        config.routing = policy.map(Box::new);
        ExecutorAction::new(
            ExecutorActionType::CodingAgentInitialRequest(
                crate::actions::coding_agent_initial::CodingAgentInitialRequest {
                    prompt: "Fix this issue".into(),
                    executor_config: config,
                    working_dir: None,
                },
            ),
            None,
        )
    }

    #[test]
    fn assessed_pairs_route_downward_without_a_routine_label() {
        let (mut p, m, mut a) = fixture();
        p.floor = CapabilityFloor::Assessed;
        for (prompt, expected) in [
            ("Fix the typo in README.md", "gpt-5.6-luna"),
            (
                "Fix button spacing in one component with an existing pattern and snapshot test",
                "gpt-6-luna",
            ),
            ("Fix an isolated bug with a regression test", "gpt-6-sol"),
            ("Implement a feature", "gpt-6.1-sol"),
            ("Investigate an intermittent failure", "gpt-6.1-sol"),
            ("Update authentication permissions", "gpt-6-astra"),
        ] {
            let assessment = crate::routing_assessment::assess(prompt);
            assert_eq!(
                choose_assessed(
                    &p,
                    p.floor.max(assessment.floor),
                    assessment.envelope,
                    &m,
                    &a,
                    100
                )
                .unwrap()
                .0,
                expected
            );
        }
        // Low effort is qualified but cannot be picked before exact execution proof.
        let first =
            choose_assessed(&p, CapabilityFloor::Routine, "mechanical", &m, &a, 100).unwrap();
        assert_eq!(first.1, "medium");
        for proof in &mut a.models {
            proof.verified_efforts.push("low".into());
            proof.supported_efforts.push("low".into());
        }
        assert_eq!(
            choose_assessed(&p, CapabilityFloor::Routine, "mechanical", &m, &a, 100)
                .unwrap()
                .1,
            "low"
        );
        // Stronger model at low effort is shadow-only until deliberately qualified.
        p.mode = RoutingMode::Shadow;
        assert_eq!(
            choose_assessed(&p, CapabilityFloor::Routine, "bounded", &m, &a, 100).unwrap(),
            ("gpt-6-sol".into(), "low".into())
        );
        p.mode = RoutingMode::Auto;
        assert_eq!(
            choose_assessed(&p, CapabilityFloor::Routine, "bounded", &m, &a, 100)
                .unwrap()
                .0,
            "gpt-6-luna"
        );
        assert_eq!(
            choose_assessed(&p, CapabilityFloor::Workhorse, "mechanical", &m, &a, 100)
                .unwrap()
                .0,
            "gpt-6.1-sol"
        );
        p.denied_models.push("gpt-6-astra".into());
        assert!(choose_assessed(&p, CapabilityFloor::Frontier, "protected", &m, &a, 100).is_err());
    }

    #[test]
    fn qualification_is_explicit_and_preference_is_configurable() {
        let (p, mut m, a) = fixture();
        for model in &mut m {
            model.qualifications.clear();
        }
        assert!(choose_assessed(&p, CapabilityFloor::Routine, "mechanical", &m, &a, 100).is_err());
        m[0].qualifications.push(Qualification {
            effort: "medium".into(),
            envelope: "mechanical".into(),
            status: QualificationStatus::Denied,
            floor: CapabilityFloor::Routine,
            preference_rank: 0,
        });
        assert!(choose_assessed(&p, CapabilityFloor::Routine, "mechanical", &m, &a, 100).is_err());
        m[0].qualifications[0].status = QualificationStatus::Qualified;
        assert_eq!(
            choose_assessed(&p, CapabilityFloor::Routine, "mechanical", &m, &a, 100)
                .unwrap()
                .0,
            "gpt-5.6-luna"
        );
    }

    #[test]
    fn shadow_followups_persist_context_and_never_change_execution_settings() {
        let (mut policy, _, _) = fixture();
        policy.mode = RoutingMode::Shadow;
        policy.floor = CapabilityFloor::Assessed;
        let mut prior = action(Some(policy.clone()));
        if let ExecutorActionType::CodingAgentInitialRequest(r) = &mut prior.typ {
            r.prompt = "Investigate an intermittent failure".into();
        }
        // Covers old persisted actions that have no structured envelope.
        for prompt in ["Fix the typo in README.md", "continue", "please continue"] {
            let template = action(Some(policy.clone()));
            let mut next = ExecutorAction::new(
                ExecutorActionType::CodingAgentFollowUpRequest(
                    crate::actions::coding_agent_follow_up::CodingAgentFollowUpRequest {
                        prompt: prompt.into(),
                        executor_config: config(&template).unwrap().clone(),
                        session_id: "existing-thread".into(),
                        reset_to_message_id: None,
                        working_dir: None,
                        capacity: None,
                    },
                ),
                None,
            );
            let before = serde_json::to_value(&next.typ).unwrap();
            resolve_action(&mut next, Some(&prior), false).unwrap();
            assert_eq!(serde_json::to_value(&next.typ).unwrap(), before);
            assert_eq!(
                next.routing_decision
                    .as_ref()
                    .unwrap()
                    .assessed_envelope
                    .as_deref(),
                Some("complex")
            );
            // Exercise the actual persistence boundary between each follow-up.
            prior = serde_json::from_value(serde_json::to_value(next).unwrap()).unwrap();
        }
        let event = crate::routing_telemetry::decision(
            &prior,
            "execution",
            "session",
            "workspace",
            None,
            "2026-09-30T00:00:00Z",
        )
        .unwrap();
        assert_eq!(event["schema"], "vk.routing.v1");
        assert_eq!(event["policyVersion"], "vk-autoswitch-v2");
        assert!(event["taskId"].is_null());
    }

    #[test]
    fn reported_validation_failure_requires_consent_before_inference() {
        let (policy, _, _) = fixture();
        let previous = action(None);
        let mut next = action(Some(policy));
        if let ExecutorActionType::CodingAgentInitialRequest(r) = &mut next.typ {
            r.prompt = "The tests still fail after that fix".into();
        }
        assert!(
            resolve_action(&mut next, Some(&previous), false)
                .unwrap_err()
                .contains("Previous execution failed")
        );
    }

    #[test]
    fn manual_is_authoritative_even_after_failure() {
        let mut a = action(None);
        let before = serde_json::to_value(&a).unwrap();
        resolve_action(&mut a, None, true).unwrap();
        assert_eq!(serde_json::to_value(a).unwrap(), before);
    }

    #[test]
    fn failure_without_consent_does_not_mutate_action() {
        let (policy, _, _) = fixture();
        let mut a = action(Some(policy));
        let before = serde_json::to_value(&a).unwrap();
        assert!(
            resolve_action(&mut a, None, true)
                .unwrap_err()
                .contains("Previous execution failed")
        );
        assert_eq!(serde_json::to_value(a).unwrap(), before);
    }

    #[test]
    fn frontier_failure_never_retries_on_a_lower_floor() {
        let (mut policy, _, _) = fixture();
        policy.allow_escalation = true;
        let previous = action(None);
        let mut next = action(Some(policy));
        assert!(
            resolve_action(&mut next, Some(&previous), true)
                .unwrap_err()
                .contains("Frontier execution failed")
        );
    }

    #[test]
    fn native_resume_preserves_model_but_obeys_new_exclusion() {
        let (mut policy, _, _) = fixture();
        let mut previous = action(None);
        previous.routing_decision = Some(Box::new(RoutingDecision {
            assessed_envelope: None,
            triage: None,
            version: 1,
            id: "prior".into(),
            mode: RoutingMode::Auto,
            floor: CapabilityFloor::Frontier,
            reason: "capability_floor".into(),
            requested_model: None,
            selected_model: Some("gpt-6-astra".into()),
            selected_effort: Some("high".into()),
            service_tier: "standard".into(),
            previous_model: None,
            previous_execution_id: None,
            escalated: false,
            catalog_observed_at: None,
            account_fingerprint: None,
        }));
        let mut config = config(&previous).unwrap().clone();
        config.model_id = Some("gpt-5.6-luna".into());
        config.routing = Some(Box::new(policy.clone()));
        let mut next = ExecutorAction::new(
            ExecutorActionType::CodingAgentFollowUpRequest(
                crate::actions::coding_agent_follow_up::CodingAgentFollowUpRequest {
                    capacity: None,
                    prompt: "/goal resume".into(),
                    session_id: "thread".into(),
                    reset_to_message_id: None,
                    executor_config: config,
                    working_dir: None,
                },
            ),
            None,
        );
        resolve_action(&mut next, Some(&previous), false).unwrap();
        assert_eq!(
            super::config(&next).unwrap().model_id.as_deref(),
            Some("gpt-6-astra")
        );
        policy.denied_models.push("gpt-6-astra".into());
        if let ExecutorActionType::CodingAgentFollowUpRequest(r) = &mut next.typ {
            r.executor_config.routing = Some(Box::new(policy));
        }
        assert!(resolve_action(&mut next, Some(&previous), false).is_err());
    }

    #[test]
    fn shadow_failure_preserves_manual_execution() {
        let (mut policy, _, _) = fixture();
        policy.mode = RoutingMode::Shadow;
        let mut a = action(Some(policy));
        let before = serde_json::to_value(&a.typ).unwrap();
        resolve_action(&mut a, None, true).unwrap();
        assert_eq!(serde_json::to_value(&a.typ).unwrap(), before);
        assert_eq!(a.routing_decision.unwrap().mode, RoutingMode::Shadow);
    }

    #[test]
    fn stronger_verified_effort_is_a_safe_fallback() {
        let (p, m, mut a) = fixture();
        for entry in &mut a.models {
            entry.verified_efforts.clear();
        }
        a.models
            .iter_mut()
            .find(|e| e.id == "gpt-6-astra")
            .unwrap()
            .verified_efforts = vec!["high".into()];
        assert_eq!(
            choose(&p, CapabilityFloor::Workhorse, &m, &a, 100).unwrap(),
            ("gpt-6-astra".into(), "high".into())
        );
    }

    #[test]
    fn least_cost_respects_floor_and_exclusions() {
        let (mut p, m, a) = fixture();
        assert_eq!(
            choose(&p, CapabilityFloor::Workhorse, &m, &a, 100)
                .unwrap()
                .0,
            "gpt-6.1-sol"
        );
        assert_eq!(
            choose(&p, CapabilityFloor::Routine, &m, &a, 100).unwrap().0,
            "gpt-6-luna"
        );
        p.denied_models.push("gpt-6-astra".into());
        assert!(choose(&p, CapabilityFloor::Frontier, &m, &a, 100).is_err());
    }
    #[test]
    fn discovery_is_neither_entitlement_nor_required_for_direct_verified_release() {
        let (p, m, mut a) = fixture();
        for item in &mut a.models {
            item.discovered = false;
        }
        assert!(choose(&p, CapabilityFloor::Workhorse, &m, &a, 100).is_ok());
        for item in &mut a.models {
            item.verified_efforts.clear();
            item.discovered = true;
        }
        assert!(choose(&p, CapabilityFloor::Workhorse, &m, &a, 100).is_err());
    }
    #[test]
    fn stale_proof_and_unsupported_effort_fail_closed() {
        let (p, m, mut a) = fixture();
        assert!(choose(&p, CapabilityFloor::Workhorse, &m, &a, 90000).is_err());
        for item in &mut a.models {
            item.supported_efforts = vec!["low".into()];
        }
        assert!(choose(&p, CapabilityFloor::Workhorse, &m, &a, 100).is_err());
    }
}

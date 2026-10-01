//! One replaceable Shadow assessment using VK's full execution-boundary resolver.
//! No execution, scheduler or DB writes. Native classification requires --semantic.
use std::io::{self, Read};

use executors::{
    actions::{ExecutorAction, ExecutorActionType},
    routing::{RoutingMode, resolve_action_with_context, resolve_action_with_semantics},
};
use serde::Deserialize;
use serde_json::json;
use uuid::Uuid;

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
struct Request {
    action: ExecutorAction,
    previous: Option<ExecutorAction>,
    previous_execution_id: Option<Uuid>,
    #[serde(default)]
    previous_failed: bool,
    repo_root: Option<std::path::PathBuf>,
}

fn evaluate(mut request: Request, semantic: bool) -> Result<serde_json::Value, String> {
    let config = match &request.action.typ {
        ExecutorActionType::CodingAgentInitialRequest(r) => &r.executor_config,
        ExecutorActionType::CodingAgentFollowUpRequest(r) => &r.executor_config,
        _ => return Err("Shadow assessment requires a coding execution".into()),
    };
    if config.routing.as_ref().map(|p| p.mode) != Some(RoutingMode::Shadow) {
        return Err("This helper only accepts explicit Shadow requests".into());
    }
    let original = request.action.typ.clone();
    let resolve = if semantic {
        resolve_action_with_semantics
    } else {
        resolve_action_with_context
    };
    resolve(
        &mut request.action,
        request.previous.as_ref(),
        request.previous_failed,
        request.repo_root.as_deref(),
    )?;
    if request.action.typ != original {
        return Err("Shadow assessment changed execution settings".into());
    }
    if let Some(decision) = request.action.routing_decision.as_mut() {
        decision.previous_execution_id = request.previous_execution_id.map(|id| id.to_string());
    }
    Ok(json!({
        "schema": "vk.shadow-assessment.v1",
        "decision": request.action.routing_decision,
        "execution_settings_changed": false,
    }))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut input = String::new();
    io::stdin().take(131_073).read_to_string(&mut input)?;
    if input.len() > 131_072 {
        return Err("Shadow request exceeds the input budget".into());
    }
    let request: Request = serde_json::from_str(&input)?;
    let semantic = std::env::args().any(|arg| arg == "--semantic");
    let output = evaluate(request, semantic).map_err(io::Error::other)?;
    println!("{output}");
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request(mode: &str, prompt: &str, floor: &str) -> Request {
        serde_json::from_value(json!({
            "action": {"typ": {"type": "CodingAgentInitialRequest", "prompt": prompt,
                "executor_config": {"executor": "CODEX", "model_id": "gpt-6.1-sol",
                    "reasoning_id": "medium", "routing": {"mode": mode, "floor": floor,
                        "denied_models": [], "allow_escalation": false}}}, "next_action": null},
            "previous": null, "previous_execution_id": null, "repo_root": null
        }))
        .unwrap()
    }

    #[test]
    fn helper_cannot_be_used_to_change_manual_or_auto_execution_settings() {
        for mode in ["manual", "auto"] {
            assert!(evaluate(request(mode, "Fix a typo in README.md", "assessed"), false).is_err());
        }
    }

    #[test]
    fn full_prior_action_releases_only_an_independent_inferred_floor() {
        let mut previous = request("shadow", "Change authentication", "assessed").action;
        resolve_action_with_context(&mut previous, None, false, None).unwrap();
        let prior_id = Uuid::new_v4();
        let mut next = request("shadow", "Fix a typo in README.md", "assessed");
        next.previous = Some(previous.clone());
        next.previous_execution_id = Some(prior_id);
        let result = evaluate(next, false).unwrap();
        assert_eq!(result["decision"]["floor"], "routine");
        assert_eq!(
            result["decision"]["previous_execution_id"],
            prior_id.to_string()
        );
        assert_eq!(result["execution_settings_changed"], false);
        let mut continuation = request("shadow", "carry on", "assessed");
        continuation.previous = Some(previous);
        assert_eq!(
            evaluate(continuation, false).unwrap()["decision"]["floor"],
            "frontier"
        );
    }

    #[test]
    fn explicit_floor_survives_shadow_assessment() {
        let result = evaluate(
            request("shadow", "Fix a typo in README.md", "frontier"),
            false,
        )
        .unwrap();
        assert_eq!(result["decision"]["floor"], "frontier");
        assert_eq!(result["decision"]["mode"], "shadow");
    }
}

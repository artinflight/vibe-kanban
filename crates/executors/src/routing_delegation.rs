//! Delegated-delta admission. Reuses V2 qualification; never chooses a model by inheritance in Auto.
use std::path::{Component, Path};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::{
    routing::{CapabilityFloor, RoutingDecision, RoutingMode, RoutingPolicy},
    routing_assessment::{assess_with_context, retain_previous},
    routing_semantic::{self, SemanticTrace},
};

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Assignment {
    pub task: String,
    pub message: String,
    pub context: String,
    pub paths: Vec<String>,
    pub independent: bool,
    /// Tiny operations belong in the parent; a batch may justify a mechanical child.
    pub size: String,
    pub read_only: bool,
}

impl Assignment {
    pub fn validate(&self, root: &Path) -> Result<(), String> {
        if self.task.is_empty()
            || self.task.len() > 64
            || !self
                .task
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
        {
            return Err("Use a stable task key of 1–64 letters, digits, '_' or '-'".into());
        }
        if self.message.trim().is_empty() || self.message.len() > 4000 || self.context.len() > 4000
        {
            return Err("Supply a focused assignment and requirements/decisions brief (each at most 4000 bytes); reference files for longer context".into());
        }
        if !self.independent || !matches!(self.size.as_str(), "batch" | "substantial") {
            return Err("Perform tiny or dependent work in the parent; delegate an independent batch or substantial subtask".into());
        }
        if self.paths.is_empty() || self.paths.len() > 8 {
            return Err("Declare 1–8 repository-relative scope paths".into());
        }
        let root = root
            .canonicalize()
            .map_err(|_| "Repository root unavailable")?;
        for name in &self.paths {
            let path = Path::new(name);
            if name.is_empty()
                || name.len() > 240
                || path
                    .components()
                    .any(|c| !matches!(c, Component::Normal(_)))
            {
                return Err(
                    "Scope paths must be relative, bounded and free of parent traversal".into(),
                );
            }
            let mut existing = root.join(path);
            while !existing.exists() {
                existing = existing
                    .parent()
                    .ok_or("Scope path has no parent")?
                    .to_path_buf();
            }
            if !existing
                .canonicalize()
                .map_err(|_| "Scope path unavailable")?
                .starts_with(&root)
            {
                return Err("Scope path escapes the repository through a symlink".into());
            }
        }
        Ok(())
    }
    pub fn fingerprint(&self) -> String {
        let mut paths = self.paths.clone();
        paths.sort();
        let message = self
            .message
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ")
            .to_lowercase();
        format!(
            "{:x}",
            Sha256::digest(format!(
                "{message}\n{}\n{paths:?}\n{}",
                self.context, self.read_only
            ))
        )
    }
    pub fn overlaps(&self, other: &Self) -> bool {
        self.paths.iter().any(|a| {
            other
                .paths
                .iter()
                .any(|b| Path::new(a).starts_with(b) || Path::new(b).starts_with(a))
        })
    }
    pub fn brief(&self, hard_floor: CapabilityFloor) -> String {
        format!(
            "Delegated assignment:\n{}\n\nRequired context/decisions:\n{}\n\nScope: {}\nInherited hard capability floor: {:?}. Follow repository instructions. Work only on this assignment; do not delegate, create goals, reset/revert existing work, or modify unrelated files. If new risk or wider scope invalidates the assignment, stop and report it. Report validation evidence and changed paths concisely; do not claim acceptance on the parent's behalf.",
            self.message,
            self.context,
            self.paths.join(", "),
            hard_floor
        )
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChildChoice {
    pub envelope: String,
    pub floor: CapabilityFloor,
    pub model: String,
    pub effort: String,
    pub source: String,
    pub semantic: Option<SemanticTrace>,
    pub escalated: bool,
}

/// Parent complexity is not a blanket child floor. Explicit/protected constraints are.
pub fn hard_floor(policy: &RoutingPolicy, parent: &RoutingDecision) -> CapabilityFloor {
    if parent.floor == CapabilityFloor::Frontier
        || parent.assessed_envelope.as_deref() == Some("protected")
    {
        CapabilityFloor::Frontier
    } else {
        policy.floor
    }
}

pub fn choose(
    assignment: &Assignment,
    root: &Path,
    policy: &RoutingPolicy,
    parent: &RoutingDecision,
    previous: Option<&ChildChoice>,
    failed: bool,
    semantic_enabled: bool,
) -> Result<ChildChoice, String> {
    assignment.validate(root)?;
    let prompt = format!(
        "{}\n{}\nScope references: {}",
        assignment.message,
        assignment.context,
        assignment.paths.join(" ")
    );
    let mut assessment = assess_with_context(&prompt, Some(root));
    let mut child_policy = policy.clone();
    child_policy.floor = hard_floor(policy, parent);
    let prior_envelope = previous.map(|p| p.envelope.as_str());
    let semantic = if semantic_enabled
        && routing_semantic::eligible(&assessment, failed, &child_policy, &prompt, prior_envelope)
    {
        let trace = routing_semantic::classify_scoped(
            &prompt,
            Some(&format!(
                "Parent envelope: {:?}; hard floor: {:?}",
                parent.assessed_envelope, child_policy.floor
            )),
            &assessment,
            &child_policy,
            serde_json::json!({"routingId":parent.id,"taskKey":assignment.task,"workKind":"delegated"}),
        );
        if let Some(class) = &trace.classification {
            routing_semantic::apply(&mut assessment, class);
        }
        Some(trace)
    } else {
        None
    };
    let mut assessment = retain_previous(assessment, &assignment.message, prior_envelope);
    let mut floor = child_policy.floor.max(assessment.floor);
    if let Some(previous) = previous {
        floor = floor.max(previous.floor);
    }
    let expanded = previous.is_some_and(|p| floor > p.floor);
    if failed {
        let previous = previous.ok_or("Failure evidence requires a prior child attempt")?;
        floor = floor.max(match previous.floor {
            CapabilityFloor::Assessed | CapabilityFloor::Routine => CapabilityFloor::Workhorse,
            CapabilityFloor::Workhorse => CapabilityFloor::Frontier,
            CapabilityFloor::Frontier => {
                return Err("Frontier child failed; operator diagnosis required".into());
            }
        });
        assessment.envelope = if floor == CapabilityFloor::Frontier {
            "protected"
        } else {
            "normal"
        };
    }
    if (failed || expanded) && !policy.allow_escalation {
        return Err(
            "Child escalation requires the operator's existing allow_escalation policy".into(),
        );
    }
    let models = crate::routing::model_policies()?;
    let availability = crate::routing::load_availability()?;
    let (model, effort) = crate::routing::choose_assessed(
        &child_policy,
        floor,
        assessment.envelope,
        &models,
        &availability,
        chrono::Utc::now().timestamp(),
    )?;
    Ok(ChildChoice {
        envelope: assessment.envelope.into(),
        floor,
        model,
        effort,
        source: assessment.evidence.into(),
        semantic,
        escalated: failed || expanded,
    })
}

pub fn actual_pair_qualified(
    choice: &ChildChoice,
    model: &str,
    effort: &str,
    policy: &RoutingPolicy,
) -> Result<bool, String> {
    let mut policy = policy.clone();
    policy.mode = RoutingMode::Auto;
    let mut models = crate::routing::model_policies()?;
    // Preserve the GLOBAL minimum-required allowlist even when checking one inherited pair.
    let protected = models.iter().any(|m| {
        m.qualifications.iter().any(|q| {
            q.envelope == choice.envelope
                && q.status == crate::routing::QualificationStatus::MinimumRequired
        })
    });
    models.retain(|m| m.id == model);
    for model in &mut models {
        model.qualifications.retain(|q| {
            q.effort == effort
                && (!protected || q.status == crate::routing::QualificationStatus::MinimumRequired)
        });
    }
    Ok(crate::routing::choose_assessed(
        &policy,
        choice.floor,
        &choice.envelope,
        &models,
        &crate::routing::load_availability()?,
        chrono::Utc::now().timestamp(),
    )
    .is_ok())
}

#[cfg(test)]
mod tests {
    use super::*;
    fn policy() -> RoutingPolicy {
        RoutingPolicy {
            mode: RoutingMode::Auto,
            floor: CapabilityFloor::Assessed,
            denied_models: vec![],
            allow_escalation: true,
        }
    }
    fn parent() -> RoutingDecision {
        serde_json::from_value(serde_json::json!({"version":2,"id":"parent","mode":"auto","floor":"workhorse","reason":"normal","assessed_envelope":"normal","service_tier":"standard","escalated":false})).unwrap()
    }
    fn assignment() -> Assignment {
        Assignment {
            task: "docs".into(),
            message: "Fix spelling typos in README.md".into(),
            context: "Preserve meaning.".into(),
            paths: vec!["README.md".into()],
            independent: true,
            size: "batch".into(),
            read_only: false,
        }
    }
    #[test]
    fn delegation_reuses_registry_and_propagates_only_hard_parent_floor() {
        let mut p = policy();
        let mut parent = parent();
        assert_eq!(hard_floor(&p, &parent), CapabilityFloor::Assessed);
        let models: Vec<crate::routing::ModelPolicy> =
            serde_json::from_str(include_str!("routing_models.json")).unwrap();
        let availability = crate::routing::Availability {
            version: 1,
            runtime: None,
            observed_at: 100,
            codex_home: String::new(),
            launcher: String::new(),
            account_fingerprint: String::new(),
            models: models
                .iter()
                .map(|m| crate::routing::ModelAvailability {
                    id: m.id.clone(),
                    discovered: true,
                    supported_efforts: m.efforts.clone(),
                    verified_efforts: m.efforts.clone(),
                    verified_at: Some(100),
                })
                .collect(),
        };
        let a = assess_with_context(&assignment().message, None);
        assert_eq!(
            crate::routing::choose_assessed(
                &p,
                hard_floor(&p, &parent).max(a.floor),
                a.envelope,
                &models,
                &availability,
                100
            )
            .unwrap(),
            ("gpt-5.6-luna".into(), "low".into())
        );
        p.floor = CapabilityFloor::Workhorse;
        assert_eq!(
            crate::routing::choose_assessed(
                &p,
                hard_floor(&p, &parent),
                a.envelope,
                &models,
                &availability,
                100
            )
            .unwrap()
            .0,
            "gpt-6.1-sol"
        );
        p.floor = CapabilityFloor::Assessed;
        parent.assessed_envelope = Some("protected".into());
        assert_eq!(hard_floor(&p, &parent), CapabilityFloor::Frontier);
        p.denied_models.push("gpt-6-astra".into());
        assert!(
            crate::routing::choose_assessed(
                &p,
                hard_floor(&p, &parent),
                a.envelope,
                &models,
                &availability,
                100
            )
            .is_err()
        );
        assert_eq!(
            assess_with_context("Fix typos in auth/permissions.rs", None).floor,
            CapabilityFloor::Frontier
        );
    }
    #[test]
    fn delegation_brief_bounds_scope_and_duplicate_requirements() {
        let root = std::env::current_dir().unwrap();
        let mut a = assignment();
        a.validate(&root).unwrap();
        let mut b = a.clone();
        b.task = "alias".into();
        assert_eq!(a.fingerprint(), b.fingerprint());
        b.context = "Different acceptance criterion".into();
        assert_ne!(a.fingerprint(), b.fingerprint());
        assert!(a.overlaps(&b));
        b.paths = vec!["src".into()];
        assert!(!a.overlaps(&b));
        a.size = "tiny".into();
        assert!(a.validate(&root).is_err());
        a.size = "batch".into();
        a.paths = vec!["../escape".into()];
        assert!(a.validate(&root).is_err());
        a.paths = vec!["src".into()];
        a.context = "x".repeat(4001);
        assert!(a.validate(&root).is_err());
    }
    #[test]
    fn delegation_failure_needs_consent_and_never_retries_frontier() {
        let root = std::env::current_dir().unwrap();
        let mut policy = policy();
        policy.allow_escalation = false;
        let mut prior = ChildChoice {
            envelope: "mechanical".into(),
            floor: CapabilityFloor::Routine,
            model: "gpt-5.6-luna".into(),
            effort: "low".into(),
            source: "fixture".into(),
            semantic: None,
            escalated: false,
        };
        assert!(
            choose(
                &assignment(),
                &root,
                &policy,
                &parent(),
                Some(&prior),
                true,
                false
            )
            .unwrap_err()
            .contains("allow_escalation")
        );
        policy.allow_escalation = true;
        prior.floor = CapabilityFloor::Frontier;
        assert!(
            choose(
                &assignment(),
                &root,
                &policy,
                &parent(),
                Some(&prior),
                true,
                false
            )
            .unwrap_err()
            .contains("operator diagnosis")
        );
    }
}

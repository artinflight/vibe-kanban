//! Cheap admission-time assessment. Positive low-risk evidence is required;
//! missing context is not evidence that a task is routine.
use super::routing::CapabilityFloor;

#[derive(Debug, PartialEq, Eq)]
pub struct Assessment {
    pub envelope: &'static str,
    pub floor: CapabilityFloor,
    pub evidence: &'static str,
    pub validation_failure: bool,
    pub triage: crate::routing_triage::TaskTriage,
}

// Match lexical boundaries rather than accepting "test" inside "latest".
fn contains_term(text: &str, term: &str) -> bool {
    text.match_indices(term).any(|(start, _)| {
        let end = start + term.len();
        let word = |c: char| c.is_alphanumeric();
        (!term.starts_with(word) || !text[..start].ends_with(word))
            && (!term.ends_with(word) || !text[end..].starts_with(word))
    })
}

// A stated non-destructive constraint is not destructive intent. Keep broad
// matching for identifiers and positive occurrences elsewhere in the request;
// this deliberately does not negate other protected categories.
fn destructive_intent(text: &str) -> bool {
    use std::sync::LazyLock;

    use regex::Regex;

    static NON_DESTRUCTIVE: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"\bnon[-‐‑ ]?destructive\b").unwrap());
    static DOUBT: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"\b(not|never|no|cannot|can't|can’t|isn't|isn’t|disable|bypass|remove|override)\s+(?:\w+\s+){0,2}$")
            .unwrap()
    });
    text.match_indices("destructive").any(|(start, _)| {
        !NON_DESTRUCTIVE
            .find_iter(text)
            .any(|m| m.start() <= start && start < m.end() && !DOUBT.is_match(&text[..m.start()]))
    })
}

fn envelope_rank(envelope: &str) -> Option<usize> {
    [
        "mechanical",
        "bounded",
        "validated_fix",
        "normal",
        "complex",
        "protected",
    ]
    .iter()
    .position(|e| *e == envelope)
}

/// Retain qualification for continuations, not unrelated work in the same chat.
/// This is not model confidence or inferred validation success.
pub fn assess_follow_up(prompt: &str, previous_envelope: Option<&str>) -> Assessment {
    assess_follow_up_with_context(prompt, previous_envelope, None)
}

pub fn assess_follow_up_with_context(
    prompt: &str,
    previous_envelope: Option<&str>,
    root: Option<&std::path::Path>,
) -> Assessment {
    retain_previous(assess_with_context(prompt, root), prompt, previous_envelope)
}

pub fn retain_previous(
    mut assessment: Assessment,
    prompt: &str,
    previous_envelope: Option<&str>,
) -> Assessment {
    let Some(previous) = previous_envelope else {
        return assessment;
    };
    let known = envelope_rank(previous).is_some();
    let previous = match previous {
        "mechanical" => "mechanical",
        "bounded" => "bounded",
        "validated_fix" => "validated_fix",
        "normal" => "normal",
        "complex" => "complex",
        _ => "protected", // Unknown persisted qualification stays fail-closed.
    };
    let bounded_step =
        known && crate::routing_context::reassess_step(&assessment, prompt, previous);
    let independent = known && (independent_request(&assessment, prompt) || bounded_step);
    if bounded_step && envelope_rank(previous) > envelope_rank(assessment.envelope) {
        assessment
            .triage
            .evidence
            .push(format!("surrounding_assignment:{previous}"));
    }
    if !independent
        && (envelope_rank(previous) > envelope_rank(assessment.envelope)
            || (is_continuation(prompt)
                && assessment.evidence == "insufficient_evidence_for_routine"))
    {
        assessment.envelope = previous;
        assessment.floor = match previous {
            "mechanical" | "bounded" => CapabilityFloor::Routine,
            "protected" => CapabilityFloor::Frontier,
            _ => CapabilityFloor::Workhorse,
        };
    }
    if !independent {
        assessment.evidence = "retained_session_qualification";
        assessment
            .triage
            .evidence
            .push("retained_session_qualification".into());
    } else {
        assessment
            .triage
            .evidence
            .push("current_request_reassessed".into());
    }
    assessment
}

/// A new request must carry positive scope evidence. Pronoun-only changes and
/// generic approvals cannot erase the task they refer to, even after a classifier call.
pub fn independent_request(a: &Assessment, prompt: &str) -> bool {
    if is_continuation(prompt) || a.validation_failure {
        return false;
    }
    let lowered = prompt.to_lowercase();
    let mut text = lowered.trim().trim_end_matches(['.', '!']);
    for suffix in [
        " and make sure it works",
        " and check it works",
        " and test it",
    ] {
        text = text.strip_suffix(suffix).unwrap_or(text);
    }
    if [
        "this",
        "that",
        "it",
        "same",
        "continue",
        "carry on",
        "remaining",
    ]
    .iter()
    .any(|term| contains_term(text, term))
    {
        return false;
    }
    // "One component" alone could still mean the previous protected component.
    // Named documentation or an inspected UI surface provides an independent target;
    // otherwise the semantic scope check must establish the relationship.
    ((a.evidence == "deterministic_text_edit"
        && (contains_term(text, "readme") || text.contains(".md")))
        || a.evidence == "triage_ui_outcome_with_repo_evidence")
        || (a
            .triage
            .evidence
            .iter()
            .any(|e| e == "semantic_independent_request")
            && a.triage.ambiguity == "low"
            && a.triage.uncertainty != "high"
            && !a.triage.needs_repo_inspection)
}

pub fn boundary_floor(
    assessment: &Assessment,
    explicit: CapabilityFloor,
    previous: Option<CapabilityFloor>,
) -> CapabilityFloor {
    let floor = explicit.max(assessment.floor);
    if assessment
        .triage
        .evidence
        .iter()
        .any(|e| e == "retained_session_qualification")
    {
        floor.max(previous.unwrap_or_default())
    } else {
        floor
    }
}

pub fn is_continuation(prompt: &str) -> bool {
    let text = prompt.trim().trim_end_matches(['.', '!']).to_lowercase();
    let text = text
        .strip_prefix("okay, ")
        .or_else(|| text.strip_prefix("ok, "))
        .unwrap_or(&text);
    matches!(
        text,
        "continue"
            | "continue please"
            | "please continue"
            | "proceed"
            | "go ahead"
            | "carry on"
            | "ready"
            | "yes"
            | "okay"
            | "ok"
            | "do it"
            | "finish it"
    )
}

pub fn assess(prompt: &str) -> Assessment {
    assess_with_context(prompt, None)
}

pub fn assess_with_context(prompt: &str, root: Option<&std::path::Path>) -> Assessment {
    let text = prompt.to_lowercase();
    let has = |words: &[&str]| words.iter().any(|w| contains_term(&text, w));
    let validation_failure = has(&[
        "tests still fail",
        "test still fails",
        "validation failed again",
        "review rejected",
        "invariant violated",
        "same failure again",
        "no verified progress",
        "fix did not work",
    ]);
    // Keep protected-risk detection broad for subsystem identifiers such as
    // authenticationService; lexical precision is a low-risk admission requirement.
    let has_risk = |words: &[&str]| words.iter().any(|w| text.contains(w));
    let (mut envelope, mut floor, mut evidence) = if has(&["auth"])
        || destructive_intent(&text)
        || has_risk(&[
            "security",
            "authentication",
            "authorization",
            "permissions",
            "permission",
            "credential",
            "credentials",
            "migration",
            "migrations",
            "delete data",
            "drop table",
            "production",
            "control plane",
            "control-plane",
            "concurrency",
            "distributed",
            "race condition",
            "cryptography",
            "cryptographic",
            "payment",
            "secret",
            "secrets",
            "access control",
            "oauth",
            "jwt",
            "encryption",
            "sudo",
            "firewall",
            "deploy",
            "deployment",
            "deploying",
            "rollback database",
        ]) {
        ("protected", CapabilityFloor::Frontier, "high_impact_intent")
    } else if has(&[
        "architecture",
        "architectural",
        "design a new",
        "ambiguous",
        "unspecified",
        "autonomous",
        "long-horizon",
        "repo-wide",
        "across the repo",
        "all subsystems",
        "from scratch",
        "novel",
        "redesign",
        "rewrite",
        "public api",
    ]) {
        (
            "complex",
            CapabilityFloor::Workhorse,
            "cross_cutting_or_open_ended",
        )
    } else if has(&[
        "debug",
        "unfamiliar",
        "root cause",
        "intermittent",
        "investigate",
        "memory leak",
    ]) {
        (
            "complex",
            CapabilityFloor::Workhorse,
            "diagnostic_uncertainty",
        )
    } else if text.len() > 4000 || prompt.lines().count() > 50 {
        (
            "normal",
            CapabilityFloor::Workhorse,
            "large_requirement_surface",
        )
    } else if has(&[
        "typo",
        "typos",
        "spelling",
        "format markdown",
        "broken link",
        "broken links",
        "rename a label",
        "update the readme",
        "fix punctuation",
    ]) && has(&[
        "readme",
        "documentation",
        "docs",
        "docs/",
        ".md",
        "label",
        "labels",
        "comment",
        "comments",
    ]) && !has(&[
        "implement",
        "refactor",
        "behavior",
        "logic",
        "api",
        "database",
        "feature",
        "script",
        "shell",
        "command",
    ]) {
        (
            "mechanical",
            CapabilityFloor::Routine,
            "deterministic_text_edit",
        )
    } else if !has(&[
        "no tests",
        "without tests",
        "untested",
        "cannot test",
        "skip tests",
        "do not run",
        "don't run",
    ]) && has(&["test", "tests", "typecheck", "lint", "snapshot"])
        && has(&[
            "single",
            "one component",
            "one file",
            "isolated",
            "localized",
            "existing pattern",
            "follow the existing",
            "same pattern",
        ])
        && !has(&["bug", "refactor", "regression", "parser", "algorithm"])
        && has(&[
            "button",
            "css",
            "spacing",
            "tooltip",
            "unit test",
            "boilerplate",
            "form label",
        ])
    {
        (
            "bounded",
            CapabilityFloor::Routine,
            "bounded_pattern_with_validation",
        )
    } else if !has(&[
        "no tests",
        "without tests",
        "untested",
        "cannot test",
        "skip tests",
        "do not run",
        "don't run",
    ]) && has(&[
        "regression test",
        "reproducing test",
        "failing test",
        "unit test",
    ]) && has(&["isolated", "single", "localized"])
        && has(&["fix", "refactor"])
    {
        (
            "validated_fix",
            CapabilityFloor::Workhorse,
            "localized_fix_with_test",
        )
    } else {
        (
            "normal",
            CapabilityFloor::Workhorse,
            "insufficient_evidence_for_routine",
        )
    };
    let mut triage = crate::routing_triage::triage(
        prompt,
        if floor == CapabilityFloor::Frontier {
            None
        } else {
            root
        },
    );
    if !triage.risk.is_empty() {
        envelope = "protected";
        floor = CapabilityFloor::Frontier;
        evidence = "triage_high_impact_outcome";
    } else if envelope == "normal"
        && !triage.needs_repo_inspection
        && triage.uncertainty == "medium"
    {
        envelope = "bounded";
        floor = CapabilityFloor::Routine;
        evidence = "triage_ui_outcome_with_repo_evidence";
    }
    if triage.intent == "unknown" {
        triage.intent = envelope.into();
        if matches!(envelope, "mechanical" | "bounded" | "validated_fix") {
            triage.scope = if envelope == "mechanical" {
                "text_only"
            } else {
                "operator_scoped"
            }
            .into();
            triage.validation = if envelope == "mechanical" {
                "direct_text_comparison"
            } else {
                "requested_not_verified"
            }
            .into();
            triage.uncertainty = if envelope == "mechanical" {
                "low"
            } else {
                "medium"
            }
            .into();
            triage.needs_repo_inspection = false;
        }
    }
    if envelope == "protected" {
        if triage.risk.is_empty() {
            triage.risk.push("explicit_high_impact_intent".into());
        }
        triage.needs_repo_inspection = false; // Already safe to require the protected tier.
        triage.uncertainty = "medium".into();
    }
    // Preserve explicit validation restrictions as hard evidence for the semantic
    // layer; missing evidence is the only normal-work default it may lower.
    if envelope == "normal"
        && has(&[
            "no tests",
            "without tests",
            "untested",
            "cannot test",
            "skip tests",
            "do not run",
            "don't run",
        ])
    {
        evidence = "validation_explicitly_unavailable";
        triage.validation = "explicitly_unavailable".into();
    }
    Assessment {
        triage,
        envelope,
        floor,
        evidence,
        validation_failure,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn lexical_evidence_does_not_confuse_incidental_substrings() {
        for prompt in [
            "Change button spacing in one component to the latest style",
            "Change button spacing in one component, use the splinter style",
            "Fix a single unit test and refactor the parser",
        ] {
            assert_ne!(assess(prompt).envelope, "bounded", "{prompt}");
        }
        for prompt in [
            "Update credentials",
            "Add migrations",
            "Change deployment settings",
            "Fix a typo in authenticationService",
            "Fix button spacing in auth_panel with a snapshot test",
        ] {
            assert_eq!(assess(prompt).envelope, "protected", "{prompt}");
        }
        assert_eq!(
            assess("Fix button spacing in one component and run tests").envelope,
            "bounded"
        );
    }

    #[test]
    fn followups_retain_relevant_context_but_release_unrelated_work() {
        assert_eq!(
            assess_follow_up("Fix the typo in README.md", Some("complex")).envelope,
            "mechanical"
        );
        assert_eq!(
            assess_follow_up("Fix the typo in README.md", Some("protected")).envelope,
            "mechanical"
        );
        for prompt in [
            "continue",
            "okay, carry on",
            "ready",
            "make it better",
            "finish the remaining work",
        ] {
            assert_eq!(
                assess_follow_up(prompt, Some("protected")).envelope,
                "protected",
                "{prompt}"
            );
        }
        assert_eq!(
            assess_follow_up("Continue.", Some("bounded")).envelope,
            "bounded"
        );
        assert_eq!(
            assess_follow_up("Implement a new feature", Some("bounded")).envelope,
            "normal"
        );
        assert_eq!(
            assess_follow_up("Change authentication", Some("bounded")).floor,
            CapabilityFloor::Frontier
        );
        assert!(assess_follow_up("Tests still fail", Some("bounded")).validation_failure);
        assert_eq!(
            assess_follow_up("continue", Some("unknown_future_envelope")).floor,
            CapabilityFloor::Frontier
        );
        let a = assess_follow_up("Fix the typo in README.md", Some("protected"));
        assert_eq!(
            boundary_floor(
                &a,
                CapabilityFloor::Assessed,
                Some(CapabilityFloor::Frontier)
            ),
            CapabilityFloor::Routine
        );
        assert_eq!(
            boundary_floor(
                &a,
                CapabilityFloor::Workhorse,
                Some(CapabilityFloor::Frontier)
            ),
            CapabilityFloor::Workhorse
        );
        assert_eq!(
            boundary_floor(&a, CapabilityFloor::Frontier, None),
            CapabilityFloor::Frontier
        );
    }

    #[test]
    fn non_destructive_constraint_does_not_create_destructive_intent() {
        for constraint in [
            "NON-DESTRUCTIVE",
            "nondestructive",
            "non destructive",
            "non‑destructive",
        ] {
            let prompt =
                format!("Continue destination-only {constraint} verification of copied media.");
            let a = assess(&prompt);
            assert_ne!(a.floor, CapabilityFloor::Frontier, "{prompt}");
            assert!(a.triage.risk.is_empty());
            assert_ne!(a.floor, CapabilityFloor::Routine);
        }
        for prompt in [
            "Do a non-destructive check, then perform destructive initialization",
            "This operation is not non-destructive",
            "We cannot guarantee non-destructive behavior",
            "Disable non-destructive safeguards",
            "Change nonDestructiveHandler",
            "Perform non-destructive production deployment verification",
            "Perform non-destructive checks in authenticationService",
            "Do non-destructive checks before the data migration",
        ] {
            assert_eq!(assess(prompt).floor, CapabilityFloor::Frontier, "{prompt}");
        }
    }

    #[test]
    fn low_risk_needs_positive_scope_evidence_and_risk_wins() {
        for (prompt, envelope) in [
            ("Fix the spelling typo in README.md", "mechanical"),
            ("Fix typos in docs", "mechanical"),
            (
                "Fix the button spacing in one component, follow the existing pattern and run its snapshot test",
                "bounded",
            ),
            (
                "Fix an isolated parser bug with a regression test",
                "validated_fix",
            ),
            ("Fix this", "normal"),
            ("Investigate an intermittent failure", "complex"),
            (
                "Fix a typo in docs/permissions.md describing production credentials",
                "protected",
            ),
            ("Design a new architecture", "complex"),
        ] {
            assert_eq!(assess(prompt).envelope, envelope, "{prompt}");
        }
        assert!(assess("The tests still fail after that fix").validation_failure);
        assert!(!assess("I am not confident").validation_failure);
    }
}

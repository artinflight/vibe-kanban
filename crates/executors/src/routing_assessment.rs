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

/// Retain qualification context across follow-ups, including terse continuations.
/// This is not model confidence or inferred validation success.
pub fn assess_follow_up(prompt: &str, previous_envelope: Option<&str>) -> Assessment {
    assess_follow_up_with_context(prompt, previous_envelope, None)
}

pub fn assess_follow_up_with_context(
    prompt: &str,
    previous_envelope: Option<&str>,
    root: Option<&std::path::Path>,
) -> Assessment {
    let mut assessment = assess_with_context(prompt, root);
    let Some(previous) = previous_envelope else {
        return assessment;
    };
    let previous = match previous {
        "mechanical" => "mechanical",
        "bounded" => "bounded",
        "validated_fix" => "validated_fix",
        "normal" => "normal",
        "complex" => "complex",
        "protected" => "protected",
        _ => "protected", // Unknown persisted qualification must not lower admission.
    };
    let continuation = matches!(
        prompt
            .trim()
            .trim_end_matches(['.', '!'])
            .to_lowercase()
            .as_str(),
        "continue" | "continue please" | "please continue" | "proceed" | "go ahead"
    );
    if continuation || envelope_rank(previous) > envelope_rank(assessment.envelope) {
        assessment.envelope = previous;
        assessment.floor = match previous {
            "mechanical" | "bounded" => CapabilityFloor::Routine,
            "protected" => CapabilityFloor::Frontier,
            _ => CapabilityFloor::Workhorse,
        };
        assessment.evidence = "retained_session_qualification";
        assessment
            .triage
            .evidence
            .push("retained_session_qualification".into());
    }
    assessment
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
            "destructive",
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
    fn followups_retain_qualification_without_inventing_failures() {
        let mut envelope = "complex";
        for prompt in ["Fix the typo in README.md", "continue", "go ahead"] {
            let assessment = assess_follow_up(prompt, Some(envelope));
            assert_eq!(assessment.envelope, "complex");
            assert!(!assessment.validation_failure);
            envelope = assessment.envelope;
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

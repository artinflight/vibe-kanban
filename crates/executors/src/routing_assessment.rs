//! Cheap admission-time assessment. Positive low-risk evidence is required;
//! missing context is not evidence that a task is routine.
use super::routing::CapabilityFloor;

#[derive(Debug, PartialEq, Eq)]
pub struct Assessment {
    pub envelope: &'static str,
    pub floor: CapabilityFloor,
    pub evidence: &'static str,
    pub validation_failure: bool,
}

pub fn assess(prompt: &str) -> Assessment {
    let text = prompt.to_lowercase();
    let has = |words: &[&str]| words.iter().any(|w| text.contains(w));
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
    let (envelope, floor, evidence) = if has(&[
        "security",
        "authentication",
        "authorization",
        "permissions",
        "credential",
        "migration",
        "delete data",
        "drop table",
        "destructive",
        "production",
        "control plane",
        "control-plane",
        "concurrency",
        "distributed",
        "race condition",
        "cryptograph",
        "payment",
        "secret",
        "access control",
        "oauth",
        "jwt",
        "encryption",
        "sudo",
        "firewall",
        "deploy",
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
        "spelling",
        "format markdown",
        "broken link",
        "rename a label",
        "update the readme",
        "fix punctuation",
    ]) && has(&[
        "readme",
        "documentation",
        "docs/",
        ".md",
        "label",
        "comment",
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
    ]) && has(&["test", "typecheck", "lint", "snapshot"])
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
    Assessment {
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
    fn low_risk_needs_positive_scope_evidence_and_risk_wins() {
        for (prompt, envelope) in [
            ("Fix the spelling typo in README.md", "mechanical"),
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

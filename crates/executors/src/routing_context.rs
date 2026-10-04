//! Small same-session context, not another planner or conversation replay.
use std::sync::LazyLock;

use regex::Regex;

use crate::{routing::CapabilityFloor, routing_assessment::Assessment};

/// The caller supplies only the immediately previous completed execution's reply.
/// Its prose resolves references; it never proves correctness or grants permission.
pub fn apply_reference_context(a: &mut Assessment, prompt: &str, reply: Option<&str>) {
    let Some(reply) = reply.filter(|s| !s.trim().is_empty()) else {
        return;
    };
    a.triage.evidence.push("completed_session_context".into());
    if a.validation_failure || !a.triage.risk.is_empty() || a.envelope != "normal" {
        return;
    }
    // Narrow zero-inference fast path: factual questions with matching report
    // content, no second instruction, attachment, operation or research request.
    let text = prompt.trim().to_lowercase();
    if text.chars().count() > 200 || text.contains(['\n', ';', '[', ']']) {
        return;
    }
    static OPERATIONS: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"\b(and|then|also|change|edit|update|delete|remove|buy|order|search|find|compare|install|run|execute|password|token|key|safe|correct|right|best|recommended|required|should|suitable|compatible|will|can|how|why)\b").unwrap()
    });
    if OPERATIONS.is_match(&text) {
        return;
    }
    static LINK: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"^(please )?((send|show|give)( me)?|i (need|want)|what is|what's|where is|where's) (the |a )?(link|url)\b[^?!.]*[?!.]*$").unwrap()
    });
    static DIMENSIONS: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"^(please )?(what (is|are)|what's) (the )?(actual |selected |chosen )?[\w -]{0,60}\b(dimensions|measurements|size)\??$").unwrap()
    });
    static UNITS: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r"\b[0-9]+(\.[0-9]+)?\s*(mm|cm|inches)\b").unwrap());
    // Multiple links/measurements need semantic disambiguation; the mere
    // presence of a URL or number does not establish the requested referent.
    static URL: LazyLock<Regex> =
        LazyLock::new(|| Regex::new(r#"https?://[^\s<>\)\]\"]+"#).unwrap());
    let links: std::collections::HashSet<_> = URL.find_iter(reply).map(|m| m.as_str()).collect();
    let known_reference = (LINK.is_match(&text) && links.len() == 1)
        || (DIMENSIONS.is_match(&text) && UNITS.find_iter(&reply.to_lowercase()).count() == 1);
    if !known_reference {
        return;
    }
    a.envelope = "bounded";
    a.floor = CapabilityFloor::Routine;
    a.evidence = "completed_context_reference_lookup";
    a.triage.intent = "reference_lookup".into();
    a.triage.scope = "localized".into();
    a.triage.pattern = "established".into();
    a.triage.ambiguity = "low".into();
    a.triage.horizon = "short".into();
    a.triage.validation = "text_comparison".into();
    a.triage.uncertainty = "low".into();
    a.triage.needs_repo_inspection = false;
    a.triage
        .evidence
        .push("completed_context_reference_lookup".into());
}

/// A cheap step must not erase the surrounding assignment's qualification.
/// Kept in extensible triage evidence so existing persisted decisions stay readable.
pub fn surrounding_envelope(decision: &crate::routing::RoutingDecision) -> Option<&str> {
    decision
        .triage
        .as_ref()?
        .evidence
        .iter()
        .find_map(|e| e.strip_prefix("surrounding_assignment:"))
}

pub fn reassess_step(a: &Assessment, prompt: &str, previous: &str) -> bool {
    let has = |s: &str| a.triage.evidence.iter().any(|e| e == s);
    if a.validation_failure
        || crate::routing_assessment::is_continuation(prompt)
        || !has("completed_session_context")
        || !a.triage.risk.is_empty()
    {
        return false;
    }
    // Investigating a symptom after a completed protected operation is still
    // complex work, not routine. Unknown cause can require inspection without
    // making the authorized diagnostic scope ambiguous. Preserve surrounding
    // qualification so later continuation cannot resume protected operations
    // at this lower floor.
    let diagnosis = has("semantic_diagnostic_step")
        && a.envelope == "complex"
        && a.floor == CapabilityFloor::Workhorse
        && a.triage.scope == "localized"
        && a.triage.horizon == "short"
        && a.triage.ambiguity == "low"
        && a.triage.uncertainty != "high";
    diagnosis
        || (a.triage.uncertainty == "low"
            && a.triage.ambiguity == "low"
            && !a.triage.needs_repo_inspection
            && matches!(a.envelope, "mechanical" | "bounded")
            && (has("completed_context_reference_lookup")
            || has("semantic_reference_lookup")
            // Same protected assignment keeps its floor for changes. A pure
            // reference lookup performs no operation in that protected system.
            || (previous != "protected" && has("semantic_bounded_step"))))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing_assessment::{assess, boundary_floor, retain_previous};

    const REPLY: &str = "Chosen component: 40 mm, https://example.invalid/component";

    #[test]
    fn known_reference_releases_inferred_history_but_not_explicit_floor() {
        let prompt = "What are the actual component dimensions?";
        let mut a = assess(prompt);
        apply_reference_context(&mut a, prompt, Some(REPLY));
        let a = retain_previous(a, prompt, Some("protected"));
        assert_eq!(a.envelope, "bounded");
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
                CapabilityFloor::Frontier,
                Some(CapabilityFloor::Frontier)
            ),
            CapabilityFloor::Frontier
        );
    }

    #[test]
    fn missing_context_operations_and_ambiguity_never_gain_reference_qualification() {
        for (prompt, reply) in [
            ("Send me the link", None),
            ("Send me the link", Some("No component has been selected")),
            ("Send me the link and delete the old entry", Some(REPLY)),
            ("Send me the secret token link", Some(REPLY)),
            (
                "What are the actual dimensions? Also change them",
                Some(REPLY),
            ),
            (
                "Send me the link",
                Some("Choices: https://example.invalid/a https://example.invalid/b"),
            ),
            (
                "What are the dimensions?",
                Some("Board: 40 mm; surface: 30 mm"),
            ),
            ("What is the safe fuse size?", Some(REPLY)),
            ("What are the right dimensions?", Some(REPLY)),
            ("Make this better", Some(REPLY)),
            ("Continue", Some(REPLY)),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, reply);
            assert!(!reassess_step(&a, prompt, "complex"), "{prompt}");
        }
    }
}

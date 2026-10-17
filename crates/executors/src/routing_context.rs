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
    // These are actual assignments, not acknowledgements or permission to
    // resume an earlier operation. Re-evaluate every current request/context;
    // no cache or stored cheap classification can override a later hard risk.
    if bounded_record_kind(prompt, reply).is_some() {
        mark_bounded(a, "completed_context_bounded_record");
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
    static LINK_PRESENTATION: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"^(?:please )?(?:(?:i )?(?:can't|cannot|can’t) click (?:the |those |these |your )?links|(?:make|render|format) (?:the |those |these |your )?links (?:clickable|as hyperlinks)|(?:show|give|send|paste)(?: me)? (?:the |those |these |your )?links)[.!?]*$").unwrap()
    });
    if OPERATIONS.is_match(&text) && !LINK_PRESENTATION.is_match(&text) {
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
    // Re-presenting a known collection does not require choosing one referent.
    // Keep this limited to presentation requests, never broken-link diagnosis,
    // hosting, access repair or changing application click behaviour.
    static SENSITIVE_URL: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"(?i)(https?://[^/\s]+@|[?&#](?:token|key|secret|password|signature|sig|auth|access_token|api_key)=)").unwrap()
    });
    let links: std::collections::HashSet<_> = URL.find_iter(reply).map(|m| m.as_str()).collect();
    let collection_presentation = LINK_PRESENTATION.is_match(&text)
        && (1..=8).contains(&links.len())
        && links.iter().all(|link| !SENSITIVE_URL.is_match(link));
    let known_reference = collection_presentation
        || (LINK.is_match(&text) && links.len() == 1 && !SENSITIVE_URL.is_match(reply))
        || (DIMENSIONS.is_match(&text) && UNITS.find_iter(&reply.to_lowercase()).count() == 1);
    if !known_reference {
        return;
    }
    mark_bounded(a, "completed_context_reference_lookup");
}

/// Exact small reporting/recording requests; never infer completion or safety.
fn bounded_record_kind(prompt: &str, reply: &str) -> Option<&'static str> {
    let text = prompt.trim().to_lowercase();
    if text.len() > 1000 || text.contains(['\n', ';', '[', ']']) {
        return None;
    }
    let prior = reply.to_lowercase();
    if [
        "tests still fail",
        "validation failed",
        "review rejected",
        "no verified progress",
        "operation failed",
        "unresolved scope",
    ]
    .iter()
    .any(|term| prior.contains(term))
    {
        return None;
    }
    // Ask about observed output, not for a new recommendation or permission to
    // resume a blocked operation. The current speech act and a matching topic
    // in completed context establish this small reporting step. A blocker in
    // another part of that report does not turn the question into remediation.
    // Keep the grammar closed: extra actions, safety judgments, unknown topics
    // and unresolved pronouns still need the normal semantic/safety path.
    static PROGRESS: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"^(?:please )?(?:do we (?:now )?have |are we (?:now )?getting |",
            r"(?:any |what(?:'s| is) the )?(?:news|updates?) on )",
            r"(?:any |better |improved |new |updated |more |fewer |",
            r"less expensive |cheaper |lower cost |lower-cost )?",
            r"(recommendations|results|reports)(?: (?:yet|now))?[.!?]*$"
        ))
        .unwrap()
    });
    if let Some(question) = PROGRESS.captures(&text) {
        let subject = &question[1];
        let topic_present = prior
            .split(|c: char| !c.is_alphanumeric())
            .any(|word| word == subject || word == subject.trim_end_matches('s'));
        // Recommend is the name of an output mode, not a request to design new
        // alternatives. Its presence resolves "recommendations" in a status
        // question even when the last reply mostly discussed validation.
        static RECOMMEND_MODE: LazyLock<Regex> =
            LazyLock::new(|| Regex::new(r"\brecommend(?:ation)? mode\b").unwrap());
        static RECORDED_RECOMMENDATIONS: LazyLock<Regex> = LazyLock::new(|| {
            Regex::new(r"\b(?:recorded|observed|generated) (?:model |routing )recommendations\b")
                .unwrap()
        });
        let known_output = if subject == "recommendations" {
            RECOMMEND_MODE.is_match(&prior) || RECORDED_RECOMMENDATIONS.is_match(&prior)
        } else {
            topic_present
        };
        if known_output {
            return Some("observed_output_status");
        }
    }
    // Inspecting storage use is not permission to free space. Require a whole
    // observational request with a closed target vocabulary; desired capacity
    // may precede it, but no operation, arbitrary suffix or unresolved target.
    // Counting multiple directories is one inventory, not cross-system edits.
    // Failure evidence above and current/native repository risk still win.
    if storage_report(&text) {
        return Some("storage_usage_report");
    }
    // A question about operator involvement is reporting, not authorization to
    // run the pending test. Require an established involvement/target reference.
    static INVOLVEMENT: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"^(?:please )?(?:do you (?:still )?need me(?: for (?:the )?([a-z0-9-]+(?: [a-z0-9-]+){0,3}))?|",
            r"is there anything (?:else )?you need from me(?: or is (?:all )?the work underway)?)[.!?]*$"
        )).unwrap()
    });
    if let Some(question) = INVOLVEMENT.captures(&text) {
        let involvement_known = [
            "human needed::",
            "manual test",
            "operator input",
            "need you",
            "waiting for you",
            "your help",
            "your input",
        ]
        .iter()
        .any(|term| prior.contains(term));
        let target_known = question.get(1).is_none_or(|target| {
            target
                .as_str()
                .split_whitespace()
                .filter(|word| !["test", "tests", "testing", "work"].contains(word))
                .all(|word| {
                    prior
                        .split(|c: char| !c.is_alphanumeric() && c != '-')
                        .any(|known| known == word)
                })
        });
        if involvement_known && target_known {
            return Some("operator_involvement_status");
        }
    }
    // Only report an established automation's configuration/status. This does
    // not promise it works, approve starting it, or repair its remaining blockers.
    static AUTOMATION_STATUS: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"^(?:(?:it(?:'s| is)|that's|that is) (?:set ?up|linked|connected),? )?",
            r"(?:will it (?:run|start) automatically(?: now)?|",
            r"is it (?:set ?up|configured) to (?:run|start) automatically)[.!?]*$"
        ))
        .unwrap()
    });
    if AUTOMATION_STATUS.is_match(&text)
        && prior.contains("automatic")
        && ["setup", "set up", "plugin", "service", "monitoring"]
            .iter()
            .any(|term| prior.contains(term))
        && prior.matches("automatic").count() == 1
        && !prior.split(|c: char| !c.is_alphanumeric()).any(|word| {
            ["services", "systems", "plugins", "automations", "monitors"].contains(&word)
        })
    {
        return Some("automation_configuration_status");
    }
    if prior.contains("blocked by") || prior.contains("cannot continue") {
        return None;
    }
    static STATUS: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"^(?:please )?(?:sitrep|status report|(?:give|show)(?: me)? (?:a |the )?status (?:report|update)|report (?:the )?(?:current )?status)[.!?]*$"
    ).unwrap()
    });
    if STATUS.is_match(&text) {
        return Some("status_report");
    }
    static NOTE: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"^(?:please )?(?:make|add|write|record|append) (?:a |the )?(?:short )?note (?:to|in) (?:the )?(?:docs|documentation|readme|changelog|[a-z0-9_./-]+\.md) (?:that|saying) .+"
    ).unwrap()
    });
    static EXTRA: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"\b(?:and then|also|afterward|afterwards|then (?:run|change|fix|replace|deploy|restart)|and (?:run|change|fix|replace|deploy|restart))\b"
    ).unwrap()
    });
    if NOTE.is_match(&text) && !EXTRA.is_match(&text) {
        return Some("documentation_record");
    }
    None
}

fn storage_report(text: &str) -> bool {
    static STORAGE_REPORT: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"^(?:(?:good|okay|ok|all right),? (?:now,? )?)?",
            r"(?:(?:we|i) (?:need|want) (?:substantially |much |some )?more ",
            r"(?:space free|free space) on (?:the )?(?:ssd|disk|drive)[.!] )?",
            r"(?:please )?(?:(?:give|show)(?: me)? (?:a |the )?report (?:of|on) |",
            r"(?:report|list|show)(?: me)? (?:the )?)",
            r"(?:large uses of space|(?:current )?(?:disk|ssd|storage) (?:usage|use)|",
            r"(?:largest|biggest) (?:files|directories|folders)(?: on (?:the )?(?:ssd|disk|drive))?)",
            r"[.!?]*$"
        ))
        .unwrap()
    });
    STORAGE_REPORT.is_match(text)
}

/// A capacity outcome alone is not a read-only inventory request. Preserve the
/// possible data-changing scope even if a semantic response calls it reporting.
/// The closed inventory grammar is the only reporting exception here.
pub(crate) fn storage_change_requested(prompt: &str) -> bool {
    let text = prompt.trim().to_lowercase();
    static CAPACITY: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(concat!(
            r"\b(?:(?:we|i) (?:need|want) (?:substantially |much |some |more )*(?:free )?(?:space|room)(?: free)? on (?:the |our |my )?(?:os |system )?(?:drive|disk|ssd)|",
            r"(?:free(?: up)?|reclaim|clear) (?:some |more |disk |storage )*(?:space|room))\b"
        )).unwrap()
    });
    CAPACITY.is_match(&text) && !storage_report(&text)
}

fn mark_bounded(a: &mut Assessment, evidence: &str) {
    a.envelope = "bounded";
    a.floor = CapabilityFloor::Routine;
    a.evidence = evidence.into();
    a.triage.intent = "reference_lookup".into();
    a.triage.scope = "localized".into();
    a.triage.pattern = "established".into();
    a.triage.ambiguity = "low".into();
    a.triage.horizon = "short".into();
    a.triage.validation = "text_comparison".into();
    a.triage.uncertainty = "low".into();
    a.triage.needs_repo_inspection = false;
    a.triage.evidence.push(evidence.into());
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

pub fn reassess_step(a: &Assessment, prompt: &str, _previous: &str) -> bool {
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
            && a.triage.scope == "localized"
            && a.triage.pattern == "established"
            && a.triage.horizon == "short"
            && a.triage.validation != "unknown"
            && !a.triage.needs_repo_inspection
            && matches!(a.envelope, "mechanical" | "bounded")
            && (has("completed_context_reference_lookup")
            || has("completed_context_bounded_record")
            || has("semantic_reference_lookup")
            // Protection belongs to relevant current work, not the chat. A
            // positively classified bounded step may release inferred history;
            // current risk, missing context and uncertainty still forbid it.
            || has("semantic_bounded_step")))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routing_assessment::{assess, boundary_floor, retain_previous};

    #[test]
    fn progress_questions_report_existing_outputs_without_resuming_blocked_work() {
        // Sanitized context shape from the observed defect; no private paths,
        // native identities or operator transcript is needed for this fixture.
        let report = "CI is blocked by an unsupported sandbox. Recommend mode and selected settings are unchanged.";
        for (prompt, reply) in [
            ("Do we have better recommendations?", report),
            ("Any news on less expensive recommendations?", report),
            ("Any update on cheaper recommendations?", report),
            ("What's the news on lower-cost recommendations?", report),
            (
                "Updates on improved results?",
                "The recorded results are available.",
            ),
            ("Are we getting better recommendations now?", report),
            ("Do we now have updated recommendations?", report),
            (
                "Do we have any results yet?",
                "The recorded results are available.",
            ),
            (
                "Are we getting improved reports?",
                "The report generator is installed.",
            ),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(a.evidence, "completed_context_bounded_record", "{prompt}");
            let a = retain_previous(a, prompt, Some("protected"));
            assert_eq!(a.floor, CapabilityFloor::Routine, "{prompt}");
            assert!(
                a.triage
                    .evidence
                    .contains(&"surrounding_assignment:protected".into())
            );
            assert_eq!(a.triage.validation, "text_comparison");
            assert!(!a.triage.needs_repo_inspection);
        }
    }

    #[test]
    fn progress_questions_require_a_resolved_reporting_step_not_new_advice() {
        let reply = "Recommend mode is unchanged; CI is blocked by the sandbox.";
        for (prompt, context) in [
            ("Do we have better recommendations?", None),
            (
                "Do we have better recommendations?",
                Some("The package is installed."),
            ),
            (
                "Do we have better recommendations?",
                Some("My recommendation is to redesign the security boundary."),
            ),
            (
                "Do we have better recommendations?",
                Some("Recommendation validation failed."),
            ),
            (
                "Do we have better recommendations?",
                Some("Recommend mode: unresolved scope."),
            ),
            (
                "Do we have better recommendations?",
                Some("Recommend mode: tests still fail."),
            ),
            (
                "Do we have better recommendations for bypassing the sandbox?",
                Some(reply),
            ),
            (
                "Do we have better recommendations? Then apply them",
                Some(reply),
            ),
            (
                "Do we have better recommendations and restart it?",
                Some(reply),
            ),
            ("Any news on cheaper recommendations?", None),
            (
                "Any news on cheaper recommendations?",
                Some("My recommendation is to replace the firewall."),
            ),
            (
                "Any news on cheaper recommendations? Apply them",
                Some(reply),
            ),
            (
                "Any news on cheaper recommendations for bypassing permissions?",
                Some(reply),
            ),
            (
                "Any news on cheaper recommendations?",
                Some("Recommend mode: tests still fail."),
            ),
            ("Are the recommendations safe?", Some(reply)),
            ("Recommend a better approach", Some(reply)),
            ("Do we have better permissions?", Some(reply)),
            ("Is it better?", Some(reply)),
            ("Fix it", Some(reply)),
            ("Continue", Some(reply)),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, context);
            assert_ne!(a.evidence, "completed_context_bounded_record", "{prompt}");
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier,
                "{prompt}"
            );
        }
        let prompt = "Do we have better recommendations?";
        for failure in [false, true] {
            let mut a = assess(prompt);
            if failure {
                a.validation_failure = true;
            } else {
                a.triage.risk.push("protected_repository_context".into());
            }
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_ne!(a.evidence, "completed_context_bounded_record");
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier
            );
        }
    }

    #[test]
    fn known_status_questions_do_not_require_operator_engineering_terms() {
        let involvement =
            "The controller responds. Dial polling still needs investigation. Human Needed:: No";
        let automation = "The monitoring plugin is installed. After linking, automatic pause still needs configuration; the camera issue remains unresolved.";
        for (prompt, reply) in [
            ("Do you need me for the dial testing?", involvement),
            ("Do you still need me?", involvement),
            (
                "Is there anything else you need from me or is all the work underway",
                involvement,
            ),
            ("It's setup, will it run automatically now?", automation),
            ("Is it configured to start automatically?", automation),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(a.evidence, "completed_context_bounded_record", "{prompt}");
            assert!(!crate::routing_semantic::needed(&a, false));
            let a = retain_previous(a, prompt, Some("protected"));
            assert_eq!(a.floor, CapabilityFloor::Routine, "{prompt}");
            assert!(
                a.triage
                    .evidence
                    .contains(&"surrounding_assignment:protected".into())
            );
            assert_eq!(
                boundary_floor(&a, CapabilityFloor::Frontier, None),
                CapabilityFloor::Frontier
            );
            assert_eq!(
                retain_previous(assess("Proceed"), "Proceed", Some("protected")).floor,
                CapabilityFloor::Frontier
            );
        }
    }

    #[test]
    fn status_fast_path_rejects_unresolved_targets_actions_failures_and_current_risk() {
        let reply = "The monitoring plugin and dial test are prepared; automatic start remains off. Human Needed:: No";
        for (prompt, context) in [
            ("Do you need me?", None),
            ("Do you need me?", Some("The file is saved.")),
            ("Do you need me for the camera testing?", Some(reply)),
            ("Do you need me? Then run the tests", Some(reply)),
            ("Do you need me to bypass approval?", Some(reply)),
            ("It's setup, run it automatically now", Some(reply)),
            ("Will it run automatically now? Also start it", Some(reply)),
            ("Will it safely run automatically now?", Some(reply)),
            ("Will it run automatically now?", None),
            (
                "Will it run automatically now?",
                Some("The package is ready."),
            ),
            (
                "Will it run automatically now?",
                Some("Two services have automatic startup configured."),
            ),
            (
                "Will it run automatically now?",
                Some("The plugin has automatic start. Validation failed."),
            ),
            (
                "Do you need me?",
                Some("Human Needed:: Yes. Tests still fail."),
            ),
            ("Is it ready?", Some(reply)),
            ("Proceed", Some(reply)),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, context);
            assert_ne!(
                a.evidence, "completed_context_bounded_record",
                "{prompt}: {context:?}"
            );
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier
            );
        }
        for prompt in ["Do you need me?", "Will it run automatically now?"] {
            for failed in [false, true] {
                let mut a = assess(prompt);
                if failed {
                    a.validation_failure = true;
                } else {
                    a.triage.risk.push("protected_repository_context".into());
                }
                apply_reference_context(&mut a, prompt, Some(reply));
                assert_ne!(a.evidence, "completed_context_bounded_record");
                assert_eq!(
                    retain_previous(a, prompt, Some("protected")).floor,
                    CapabilityFloor::Frontier
                );
            }
        }
    }

    #[test]
    fn capacity_outcome_cannot_be_reinterpreted_as_a_report() {
        let reply = "The earlier cleanup is complete. A disk-usage report is available.";
        for prompt in [
            "We need space on OS drive",
            "I need more room on the system disk",
            "We want substantially more free space on our SSD",
            "Please free up some disk space",
            "Reclaim storage space",
            "Show me disk usage. Then free space",
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(a.floor, CapabilityFloor::Frontier, "{prompt}");
            assert!(!a.triage.risk.is_empty());
            // Replay the observed erroneous risk-free semantic result. A new
            // or existing session must retain the capacity request's real scope.
            let c: crate::routing_semantic::SemanticClass =
                serde_json::from_value(serde_json::json!({
                    "envelope":"bounded", "scope_relation":"bounded_step", "scope":"localized",
                    "novelty":"established", "ambiguity":"low", "horizon":"short",
                    "validation":"text_comparison", "risks":[], "uncertainty":"low",
                    "inspection_needed":false, "reason":"A report of existing capacity."
                }))
                .unwrap();
            crate::routing_semantic::apply_for_request(&mut a, &c, prompt);
            assert_eq!(a.floor, CapabilityFloor::Frontier, "{prompt}");
        }
        for prompt in ["Show me disk usage", "Give me a report on storage usage"] {
            assert!(!storage_change_requested(prompt));
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(a.floor, CapabilityFloor::Routine);
        }
    }

    #[test]
    fn storage_inventory_is_reporting_not_cleanup_or_cross_system_change() {
        let reply = "The earlier cleanup operation is complete; further removal is blocked by retention policy.";
        for prompt in [
            "Good, now, we need substantially more space free on SSD. Give me a report of large uses of space",
            "Show me disk usage",
            "Please list the largest directories on the SSD",
            "Give me a report on storage usage",
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(a.evidence, "completed_context_bounded_record", "{prompt}");
            assert!(!crate::routing_semantic::needed(&a, false));
            let a = retain_previous(a, prompt, Some("protected"));
            assert_eq!(a.floor, CapabilityFloor::Routine, "{prompt}");
            assert!(
                a.triage
                    .evidence
                    .contains(&"surrounding_assignment:protected".into())
            );
            assert_eq!(
                boundary_floor(&a, CapabilityFloor::Frontier, None),
                CapabilityFloor::Frontier
            );
        }
        for prompt in [
            "Give me a report of large uses of space and delete the biggest files",
            "Show me disk usage. Then free space",
            "List the largest directories and fix permissions",
            "List the largest files including passwords",
            "Show me storage usage for production data migration",
            "Show me disk usage; disable retention checks",
            "We need more space free on SSD. Delete the largest directories",
            "Show me its usage",
            "Is it safe to remove the largest directories?",
            "Continue",
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_ne!(a.evidence, "completed_context_bounded_record", "{prompt}");
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier,
                "{prompt}"
            );
        }
        for reply in [None, Some("Validation failed; no verified progress.")] {
            let prompt = "Show me disk usage";
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, reply);
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier
            );
        }
        for failure in [false, true] {
            let prompt = "Show me disk usage";
            let mut a = assess(prompt);
            if failure {
                a.validation_failure = true;
            } else {
                a.triage.risk.push("protected_repository_context".into());
            }
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier
            );
        }
    }

    #[test]
    fn bounded_reports_and_documentation_do_not_resume_protected_work() {
        let reply = "The previous response is complete; the facts and result are recorded.";
        for prompt in [
            "Sitrep",
            "Give me a status update",
            "Make a note to docs that I borrowed a fastener from the older device, so when it is repaired we remember to replace it",
            "Add a note in README.md saying the earlier test used the spare connector",
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            assert_eq!(a.envelope, "bounded", "{prompt}");
            let a = retain_previous(a, prompt, Some("protected"));
            assert_eq!(a.floor, CapabilityFloor::Routine, "{prompt}");
            assert!(
                a.triage
                    .evidence
                    .contains(&"surrounding_assignment:protected".into())
            );
            assert_eq!(
                boundary_floor(&a, CapabilityFloor::Frontier, None),
                CapabilityFloor::Frontier
            );
            assert_eq!(
                boundary_floor(&a, CapabilityFloor::Workhorse, None),
                CapabilityFloor::Workhorse
            );
        }
    }

    #[test]
    fn reporting_fast_path_requires_resolved_context_and_current_safe_scope() {
        for (prompt, reply) in [
            ("Sitrep", None),
            ("Sitrep", Some("")),
            ("Sitrep", Some("Validation failed; operation failed.")),
            ("Continue", Some("An operation is complete.")),
            ("Yes", Some("An operation is complete.")),
            ("Sitrep and restart it", Some("An operation is complete.")),
            (
                "Make a note to docs that the check ran; then change the code",
                Some("A check is complete."),
            ),
            (
                "Make a note to docs that a part was borrowed and replace the part",
                Some("A check is complete."),
            ),
            (
                "Make a note to docs that the password is available",
                Some("A check is complete."),
            ),
            ("Tests still fail", Some("A check is complete.")),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, reply);
            assert_ne!(a.evidence, "completed_context_bounded_record", "{prompt}");
            assert_eq!(
                retain_previous(a, prompt, Some("protected")).floor,
                CapabilityFloor::Frontier
            );
        }
        let mut a = assess("Sitrep");
        a.triage.risk.push("protected_repository_context".into());
        apply_reference_context(&mut a, "Sitrep", Some("The previous step is complete."));
        assert_ne!(a.evidence, "completed_context_bounded_record");
    }

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

    #[test]
    fn known_link_collection_is_presentation_not_protected_project_work() {
        let reply = "Preview https://example.invalid/preview; PR https://example.invalid/pr";
        for prompt in [
            "Can't click those links",
            "Please make the links clickable",
            "Paste me the links",
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(reply));
            let a = retain_previous(a, prompt, Some("protected"));
            assert_eq!(a.envelope, "bounded", "{prompt}");
            assert_eq!(a.floor, CapabilityFloor::Routine);
            assert!(
                a.triage
                    .evidence
                    .contains(&"surrounding_assignment:protected".into())
            );
            assert_eq!(
                boundary_floor(&a, CapabilityFloor::Frontier, None),
                CapabilityFloor::Frontier
            );
        }
        for (prompt, context) in [
            ("Which link should I use?", reply),
            ("Fix the links in the app", reply),
            ("The links return access denied", reply),
            ("Make the links clickable and deploy", reply),
            ("Can't click those links", "No links supplied"),
            (
                "Can't click those links",
                "https://example.invalid/?token=private",
            ),
            (
                "Can't click those links",
                "https://user:password@example.invalid/",
            ),
        ] {
            let mut a = assess(prompt);
            apply_reference_context(&mut a, prompt, Some(context));
            assert_ne!(a.evidence, "completed_context_reference_lookup", "{prompt}");
        }
    }
}

//! Bounded, zero-inference outcome triage. Repository text is evidence, never instructions.
#[cfg(not(test))]
use std::time::Instant;
use std::{io::Read, path::Path, sync::LazyLock, time::Duration};

use regex::Regex;
use serde::{Deserialize, Serialize};
use ts_rs::TS;

#[cfg(test)]
use self::tests::InspectionInstant as Instant;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, TS)]
pub struct TaskTriage {
    pub version: u32,
    pub intent: String,
    pub scope: String,
    pub pattern: String,
    pub ambiguity: String,
    pub horizon: String,
    pub validation: String,
    pub risk: Vec<String>,
    /// Evidence strength, not a model's self-reported probability of success.
    pub uncertainty: String,
    pub needs_repo_inspection: bool,
    pub evidence: Vec<String>,
    pub inspected_entries: u32,
    pub inspected_files: u32,
}

#[derive(Default, Debug)]
struct RepoEvidence {
    surface: bool,
    pattern: bool,
    validation: bool,
    protected: bool,
    incomplete: bool,
    entries: u32,
    files: u32,
}

fn read_small(path: &Path) -> Option<String> {
    let meta = std::fs::symlink_metadata(path).ok()?;
    if !meta.is_file() || meta.len() > 16384 {
        return None;
    }
    let mut text = String::new();
    std::fs::File::open(path)
        .ok()?
        .take(16385)
        .read_to_string(&mut text)
        .ok()?;
    (text.len() <= 16384).then_some(text)
}

fn protected_context(text: &str) -> bool {
    static PROTECTED: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(
        r"(?i)(authentication|authorization|permissions?|migrations?|credentials?|payments?|concurrency|control[_ -]plane|\bauth\b|useauth|authprovider|authcontext)"
    ).unwrap()
    });
    PROTECTED.is_match(text)
}

fn inspect(root: &Path, surface: &str, tooltip: bool, budget: Duration) -> RepoEvidence {
    let mut result = RepoEvidence::default();
    let Ok(root) = root.canonicalize() else {
        result.incomplete = true;
        return result;
    };
    let start = Instant::now();

    // Deliberately scoped to conventional UI trees, never all repository contents.
    for prefix in [
        "src",
        "app",
        "frontend/src",
        "web/src",
        "packages/web-core/src",
        "packages/local-web/src",
        "components",
        "pages",
    ] {
        let dir = root.join(prefix);
        if !dir.is_dir() {
            continue;
        }
        if !dir.canonicalize().is_ok_and(|p| p.starts_with(&root))
            || dir
                .symlink_metadata()
                .is_ok_and(|m| m.file_type().is_symlink())
        {
            result.incomplete = true;
            continue;
        }
        for entry in walkdir::WalkDir::new(&dir)
            .follow_links(false)
            .max_depth(8)
            .into_iter()
            .filter_entry(|e| {
                !["node_modules", "target", "dist", "build", ".git"]
                    .contains(&e.file_name().to_str().unwrap_or(""))
                    && !e.file_type().is_symlink()
            })
        {
            if result.entries >= 768 || start.elapsed() >= budget || result.files >= 8 {
                result.incomplete = true;
                return result;
            }
            result.entries += 1;
            let Ok(entry) = entry else {
                result.incomplete = true;
                continue;
            };
            if !entry.file_type().is_file() {
                continue;
            }
            let name = entry.file_name().to_string_lossy().to_lowercase();
            if !["tsx", "jsx", "vue", "svelte"].contains(
                &entry
                    .path()
                    .extension()
                    .and_then(|e| e.to_str())
                    .unwrap_or(""),
            ) {
                continue;
            }
            let stem = entry
                .path()
                .file_stem()
                .and_then(|s| s.to_str())
                .unwrap_or("")
                .to_lowercase()
                .replace(['-', '_'], "");
            let normalized_surface = surface.replace('-', "");
            let is_surface = ["", "page", "screen", "dialog", "panel", "form", "menu"]
                .iter()
                .any(|suffix| stem == format!("{normalized_surface}{suffix}"))
                || (["index", "page"].contains(&stem.as_str())
                    && entry
                        .path()
                        .parent()
                        .and_then(|p| p.file_name())
                        .is_some_and(|p| p.to_string_lossy().to_lowercase() == surface));
            let is_pattern = tooltip
                && name.contains("tooltip")
                && !name.contains(".test.")
                && !name.contains(".spec.");
            if !is_surface && !is_pattern {
                continue;
            }
            result.files += 1;
            let Some(text) = read_small(entry.path()) else {
                result.incomplete = true;
                continue;
            };
            if is_surface {
                result.surface = true;
                result.protected |= protected_context(
                    &entry
                        .path()
                        .strip_prefix(&root)
                        .unwrap_or(entry.path())
                        .to_string_lossy(),
                ) || protected_context(&text);
                result.pattern |= !tooltip || text.contains("Tooltip") || text.contains("tooltip");
                // Look only at package manifests belonging to this component.
                for parent in entry.path().ancestors().skip(1).take(10) {
                    if !parent.starts_with(&root) {
                        break;
                    }
                    if !parent.join("package.json").is_file() {
                        continue;
                    }
                    if result.files >= 8 || start.elapsed() >= budget {
                        result.incomplete = true;
                        return result;
                    }
                    result.files += 1;
                    if let Some(manifest) = read_small(&parent.join("package.json")) {
                        let value: serde_json::Value =
                            serde_json::from_str(&manifest).unwrap_or_default();
                        result.validation |= value
                            .get("scripts")
                            .and_then(|v| v.as_object())
                            .is_some_and(|scripts| {
                                ["test", "check", "typecheck", "lint"].iter().any(|key| {
                                    scripts.get(*key).and_then(|v| v.as_str()).is_some_and(
                                        |command| {
                                            [
                                                "tsc",
                                                "vue-tsc",
                                                "svelte-check",
                                                "vitest",
                                                "jest",
                                                "eslint",
                                                "playwright",
                                            ]
                                            .contains(
                                                &command.split_whitespace().next().unwrap_or(""),
                                            )
                                        },
                                    )
                                })
                            });
                    }
                }
            }
            result.pattern |= is_pattern;
            if result.protected || (result.surface && result.pattern && result.validation) {
                return result;
            }
        }
    }
    result
}

/// Facts read by VK, separately from replaceable prompt interpretation. A named
/// component can be protected even when the request includes harmless cautions.
pub fn repository_context(prompt: &str, root: Option<&Path>) -> TaskTriage {
    let mut result = unknown();
    // A bounded classifier must not silently miss requirements beyond its input.
    // This is an observed budget fact, independent of any prompt-language rule.
    if prompt.chars().nth(6144).is_some() {
        result
            .risk
            .push("classification_input_exceeds_bound".into());
        result
            .evidence
            .push("request_not_fully_visible_to_module".into());
    }
    let Some(root) = root else {
        return result;
    };
    static SURFACE: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"\b([a-z][a-z0-9-]{2,24}) (page|screen|dialog|panel|form|menu)\b").unwrap()
    });
    let text = prompt.to_lowercase();
    let mut surfaces = SURFACE.captures_iter(&text);
    let Some(surface) = surfaces.next() else {
        return result;
    };
    if surfaces.next().is_some() {
        return result;
    }
    let repo = inspect(root, &surface[1], true, Duration::from_millis(40));
    result.inspected_entries = repo.entries;
    result.inspected_files = repo.files;
    if repo.protected {
        result.risk.push("protected_component_context".into());
        result
            .evidence
            .push("matched_component_references_protected_subsystem".into());
    }
    if repo.surface {
        result.evidence.push("existing_ui_surface".into());
    }
    if repo.pattern {
        result.pattern = "existing_ui_pattern".into();
    }
    if repo.validation {
        result.validation = "package_check_available_not_run".into();
    }
    if repo.incomplete {
        result
            .evidence
            .push("inspection_incomplete_or_budget_exhausted".into());
    }
    result.needs_repo_inspection =
        !(repo.surface && repo.pattern && repo.validation && !repo.incomplete);
    result
}

fn unknown() -> TaskTriage {
    TaskTriage {
        version: 1,
        intent: "unknown".into(),
        scope: "unknown".into(),
        pattern: "unknown".into(),
        ambiguity: "high".into(),
        horizon: "unknown".into(),
        validation: "unknown".into(),
        risk: vec![],
        uncertainty: "high".into(),
        needs_repo_inspection: true,
        evidence: vec![],
        inspected_entries: 0,
        inspected_files: 0,
    }
}

/// Infer an outcome + object + surface, then corroborate inexpensive implementation evidence.
/// Unknown or compound outcomes remain unknown instead of requiring engineering labels.
pub fn triage(prompt: &str, root: Option<&Path>) -> TaskTriage {
    let text = prompt.to_lowercase();
    let has = |terms: &[&str]| terms.iter().any(|term| text.contains(term));
    let mut result = unknown();
    // Plain-language consequences override apparently small visual changes.
    if has(&[
        "sign in",
        "log in",
        "login",
        "password",
        "who can",
        "anyone can access",
        "everyone can access",
        "only admins",
        "other people's",
        "other users'",
        "without signing in",
        "remember me",
        "credit card",
        "checkout",
        "billing",
    ]) || (has(&["delete", "erase", "remove"])
        && has(&[
            "records",
            "accounts",
            "customer data",
            "all data",
            "old data",
        ]))
        || has(&[
            "at the same time",
            "keep devices in sync",
            "across devices",
            "without losing data",
        ])
    {
        result.intent = "protected_change".into();
        result.risk.push("access_data_or_shared_state".into());
        result
            .evidence
            .push("requested_outcome_has_high_impact_consequences".into());
        result.uncertainty = "medium".into();
        return result;
    }
    static SURFACE: LazyLock<Regex> = LazyLock::new(|| {
        Regex::new(r"\b([a-z][a-z0-9-]{2,24}) (page|screen|dialog|panel|form|menu)\b").unwrap()
    });
    let surfaces: Vec<_> = SURFACE
        .captures_iter(&text)
        .map(|c| (c[1].to_owned(), c.get(0).unwrap().end()))
        .collect();
    if surfaces.len() != 1 {
        return result;
    }
    // Unknown trailing requirements are additional scope, not validation evidence.
    let suffix = text[surfaces[0].1..]
        .trim()
        .trim_start_matches(',')
        .trim()
        .trim_end_matches(['.', '!']);
    if !matches!(
        suffix,
        "" | "please"
            | "and make sure it works"
            | "and check it works"
            | "and test it"
            | "and make sure it looks right"
    ) {
        return result;
    }
    let tooltip = has(&[
        "tooltip",
        "help text",
        "help bubble",
        "hint when",
        "explanation when",
    ]);
    let presentation = tooltip
        || has(&[
            "spacing",
            "font size",
            "text size",
            "button label",
            "button color",
            "button colour",
        ]);
    let action = has(&[
        "add ",
        "show ",
        "put ",
        "change ",
        "make ",
        "give ",
        "display ",
        "increase ",
        "reduce ",
    ]);
    // A second requested operation is not made cheap by also asking for a tooltip.
    let clauses_safe = text.split(" and ").skip(1).all(|c| {
        matches!(
            c.trim().trim_end_matches(['.', '!']),
            "make sure it works" | "check it works" | "test it" | "make sure it looks right"
        )
    });
    if !presentation
        || !action
        || surfaces.len() != 1
        || !clauses_safe
        || text.len() > 500
        || text.trim().trim_end_matches('.').contains('.')
        || has(&[
            "every",
            "all pages",
            "across",
            "new page",
            "redesign",
            "automatically",
            "depending on",
            "for each",
            " then ",
            " also ",
            "save ",
            "send ",
            "export",
            "calculate",
            ";",
            "\n",
        ])
    {
        return result;
    }
    result.intent = if tooltip {
        "ui_help"
    } else {
        "ui_presentation"
    }
    .into();
    result.scope = "single_surface_likely".into();
    result.ambiguity = "low".into();
    result.horizon = "short".into();
    result
        .evidence
        .push("concrete_presentation_outcome_on_named_surface".into());
    let Some(root) = root else {
        return result;
    };
    let repo = inspect(root, &surfaces[0].0, tooltip, Duration::from_millis(40));
    result.inspected_entries = repo.entries;
    result.inspected_files = repo.files;
    if repo.protected {
        result.risk.push("protected_component_context".into());
        result
            .evidence
            .push("matched_component_references_protected_subsystem".into());
    }
    if repo.surface {
        result.evidence.push("existing_ui_surface".into());
    }
    if repo.pattern {
        result.pattern = "existing_ui_pattern".into();
    }
    if repo.validation {
        result.validation = "package_check_available_not_run".into();
    }
    if repo.incomplete {
        result
            .evidence
            .push("inspection_incomplete_or_budget_exhausted".into());
    }
    let supported = repo.surface && repo.pattern && repo.validation && !repo.incomplete;
    if supported {
        result.uncertainty = "medium".into();
        result.needs_repo_inspection = false;
    }
    result
}

#[cfg(test)]
mod tests {
    use std::{cell::Cell, time::Duration};

    use crate::{routing::CapabilityFloor, routing_assessment::assess_with_context};

    thread_local! {
        // Fixture correctness must not depend on a CI worker being scheduled
        // inside the production 40 ms inspection budget. No production knob.
        static INSPECTION_ELAPSED: Cell<Option<Duration>> = const { Cell::new(None) };
    }

    pub(super) struct InspectionInstant(std::time::Instant);
    impl InspectionInstant {
        pub(super) fn now() -> Self {
            Self(std::time::Instant::now())
        }

        pub(super) fn elapsed(&self) -> Duration {
            INSPECTION_ELAPSED.get().unwrap_or_else(|| self.0.elapsed())
        }
    }

    struct InspectionClock(Option<Duration>);
    impl InspectionClock {
        fn at(elapsed: Duration) -> Self {
            Self(INSPECTION_ELAPSED.replace(Some(elapsed)))
        }
    }
    impl Drop for InspectionClock {
        fn drop(&mut self) {
            INSPECTION_ELAPSED.set(self.0);
        }
    }

    struct Repo {
        root: std::path::PathBuf,
        _clock: InspectionClock,
    }
    impl Repo {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!("vk-triage-{}", uuid::Uuid::new_v4()));
            std::fs::create_dir_all(path.join("src/pages")).unwrap();
            std::fs::write(
                path.join("package.json"),
                r#"{"scripts":{"check":"tsc --noEmit"}}"#,
            )
            .unwrap();
            std::fs::write(
                path.join("src/pages/Settings.tsx"),
                "export function Settings() { return <Tooltip>Settings</Tooltip>; }",
            )
            .unwrap();
            Self {
                root: path,
                _clock: InspectionClock::at(Duration::ZERO),
            }
        }
    }
    impl Drop for Repo {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.root);
        }
    }

    #[test]
    fn natural_requests_use_repo_evidence_not_engineering_labels() {
        let repo = Repo::new();
        for prompt in [
            "Add a tooltip to the settings page and make sure it works",
            "Please put some help text on the settings screen",
            "Make the button colour brighter on the settings page",
        ] {
            let result = assess_with_context(prompt, Some(&repo.root));
            assert_eq!(result.envelope, "bounded", "{prompt}");
            assert_eq!(result.floor, CapabilityFloor::Routine);
            assert_eq!(result.triage.validation, "package_check_available_not_run");
            assert!(!result.triage.needs_repo_inspection);
            assert!(result.triage.inspected_files <= 8);
        }
    }

    #[test]
    fn immutable_repository_context_survives_scope_cautions_and_changes_to_prompt_rules() {
        let repo = Repo::new();
        let prompt = "Add a tooltip to the settings page. No production deployment.";
        let context = super::repository_context(prompt, Some(&repo.root));
        assert!(context.risk.is_empty());
        assert!(!context.needs_repo_inspection);
        assert!(context.inspected_files > 0 && context.inspected_files <= 8);
        assert_eq!(context.intent, "unknown"); // facts, not a second classifier
        std::fs::write(repo.root.join("src/pages/Settings.tsx"),
            "import {checkPermissions} from './permissions'; export const Settings = () => <Tooltip/>;").unwrap();
        let context = super::repository_context(prompt, Some(&repo.root));
        assert!(context.risk.contains(&"protected_component_context".into()));
        let mut assessment = crate::routing_assessment::assess(prompt);
        crate::routing_assessment::apply_repository_context(&mut assessment, &context);
        assert_eq!(assessment.floor, CapabilityFloor::Frontier);
    }

    #[test]
    fn omitted_prompt_tail_cannot_hide_risk_from_bounded_module() {
        let prompt = format!(
            "Fix spelling typos in README.md. {} Change authentication permissions.",
            " ".repeat(6144)
        );
        let context = super::repository_context(&prompt, None);
        assert!(
            context
                .risk
                .contains(&"classification_input_exceeds_bound".into())
        );
        let mut assessment = crate::routing_assessment::assess("Fix spelling typos in README.md");
        crate::routing_assessment::apply_repository_context(&mut assessment, &context);
        assert_eq!(assessment.floor, CapabilityFloor::Frontier);
    }

    #[test]
    fn unknown_context_or_unrelated_components_cannot_justify_downward_routing() {
        let prompt = "Add a tooltip to the settings page and make sure it works";
        let missing = assess_with_context(prompt, None);
        assert_eq!(missing.floor, CapabilityFloor::Workhorse);
        assert_eq!(missing.triage.scope, "single_surface_likely");
        assert_eq!(missing.triage.uncertainty, "high");
        let repo = Repo::new();
        std::fs::rename(
            repo.root.join("src/pages/Settings.tsx"),
            repo.root.join("src/pages/SettingsButton.tsx"),
        )
        .unwrap();
        assert_eq!(
            assess_with_context(prompt, Some(&repo.root)).floor,
            CapabilityFloor::Workhorse
        );
        std::fs::rename(
            repo.root.join("src/pages/SettingsButton.tsx"),
            repo.root.join("src/pages/Settings.tsx"),
        )
        .unwrap();
        std::fs::write(
            repo.root.join("package.json"),
            r#"{"scripts":{"test":"echo no tests yet"}}"#,
        )
        .unwrap();
        assert_eq!(
            assess_with_context(prompt, Some(&repo.root)).floor,
            CapabilityFloor::Workhorse
        );
    }

    #[test]
    fn simple_language_and_discovered_protected_context_raise_the_floor() {
        let repo = Repo::new();
        for prompt in [
            "Let anyone open the settings page without signing in",
            "Remove old customer data",
            "Make settings work across devices",
            "Add a tooltip to the billing page",
        ] {
            assert_eq!(
                assess_with_context(prompt, Some(&repo.root)).floor,
                CapabilityFloor::Frontier,
                "{prompt}"
            );
        }
        std::fs::write(repo.root.join("src/pages/Settings.tsx"), "import {checkPermissions} from './permissions'; export const Settings = () => <Tooltip/>;").unwrap();
        let result = assess_with_context("Add a tooltip to the settings page", Some(&repo.root));
        assert_eq!(
            result.floor,
            CapabilityFloor::Frontier,
            "{:?}",
            result.triage
        );
        assert!(
            result
                .triage
                .risk
                .contains(&"protected_component_context".into())
        );
    }

    #[test]
    fn exhausted_inspection_budget_preserves_unknown_context() {
        let repo = Repo::new();
        let inspected = super::inspect(&repo.root, "settings", true, std::time::Duration::ZERO);
        assert!(inspected.incomplete);
        assert!(!inspected.surface);
        assert!(!inspected.protected);
        assert_eq!(inspected.entries, 0);
    }

    #[test]
    fn exhausted_inspection_budget_stays_incomplete_and_preserves_explicit_risk() {
        let repo = Repo::new();
        std::fs::write(
            repo.root.join("src/pages/Settings.tsx"),
            "import {checkPermissions} from './permissions'; export const Settings = () => <Tooltip/>;",
        )
        .unwrap();
        let _expired = InspectionClock::at(Duration::from_millis(41));
        let result = assess_with_context("Add a tooltip to the settings page", Some(&repo.root));
        // Budget exhaustion does not prove routine scope. With no component
        // inspected, retain the existing unknown-context floor, not a new policy.
        assert_eq!(result.floor, CapabilityFloor::Workhorse);
        assert!(result.triage.needs_repo_inspection);
        assert_eq!(result.triage.inspected_entries, 0);
        assert!(
            result
                .triage
                .evidence
                .contains(&"inspection_incomplete_or_budget_exhausted".into())
        );
        assert_eq!(
            assess_with_context("Add a tooltip to the billing page", Some(&repo.root)).floor,
            CapabilityFloor::Frontier
        );
    }

    #[test]
    fn inspection_clock_is_nested_thread_local_and_restored() {
        assert!(INSPECTION_ELAPSED.get().is_none());
        {
            let _fixture = InspectionClock::at(Duration::ZERO);
            {
                let _expired = InspectionClock::at(Duration::from_millis(41));
                assert_eq!(
                    InspectionInstant::now().elapsed(),
                    Duration::from_millis(41)
                );
            }
            assert_eq!(InspectionInstant::now().elapsed(), Duration::ZERO);
            std::thread::spawn(|| assert!(INSPECTION_ELAPSED.get().is_none()))
                .join()
                .unwrap();
        }
        assert!(INSPECTION_ELAPSED.get().is_none());
    }

    #[cfg(unix)]
    #[test]
    fn repo_inspection_does_not_follow_source_symlinks() {
        let repo = Repo::new();
        let external = Repo::new();
        std::fs::remove_dir_all(repo.root.join("src")).unwrap();
        std::os::unix::fs::symlink(external.root.join("src"), repo.root.join("src")).unwrap();
        let result = assess_with_context("Add a tooltip to the settings page", Some(&repo.root));
        assert_eq!(result.floor, CapabilityFloor::Workhorse);
        assert_eq!(result.triage.inspected_files, 0);
        assert!(result.triage.needs_repo_inspection);
    }

    #[test]
    fn ambiguity_compound_work_and_incomplete_reads_stay_conservative() {
        let repo = Repo::new();
        for prompt in [
            "Make the settings page better",
            "Add a tooltip to the settings page and export all records",
            "Add a tooltip to every settings page",
            "Add a tooltip to the settings page then change how accounts work",
            "Add a tooltip to the settings page that remembers preferences",
        ] {
            assert_ne!(
                assess_with_context(prompt, Some(&repo.root)).floor,
                CapabilityFloor::Routine,
                "{prompt}"
            );
        }
        std::fs::write(repo.root.join("src/pages/Settings.tsx"), "x".repeat(16385)).unwrap();
        let result = assess_with_context("Add a tooltip to the settings page", Some(&repo.root));
        assert_eq!(result.floor, CapabilityFloor::Workhorse);
        assert!(result.triage.needs_repo_inspection);
    }
}

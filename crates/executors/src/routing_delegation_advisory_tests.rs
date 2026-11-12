//! Policy regressions; also compiled from exact production sources by the narrow
//! offline harness when the host's Cargo dependency cache is unavailable.
use super::*;
use crate::routing::{
    Availability, ModelAvailability, ModelPolicy, Qualification, QualificationStatus,
    choose_assessed,
};

pub(super) fn fixture() -> (RoutingPolicy, Vec<ModelPolicy>, Availability) {
    let policy = RoutingPolicy {
        mode: RoutingMode::Shadow,
        floor: CapabilityFloor::Assessed,
        denied_models: vec![],
        allow_escalation: false,
    };
    let models = vec![
        ModelPolicy {
            id: "gpt-6.1-sol".into(),
            released: true,
            efforts: vec!["low".into(), "medium".into(), "high".into(), "xhigh".into()],
            floor: CapabilityFloor::Workhorse,
            cost_rank: 1,
            qualifications: vec![],
        },
        ModelPolicy {
            id: "gpt-6-astra".into(),
            released: true,
            efforts: vec!["high".into()],
            floor: CapabilityFloor::Frontier,
            cost_rank: 2,
            qualifications: vec![Qualification {
                effort: "high".into(),
                envelope: "protected".into(),
                status: QualificationStatus::MinimumRequired,
                floor: CapabilityFloor::Frontier,
                preference_rank: 2,
            }],
        },
    ];
    let availability = Availability {
        version: 1,
        observed_at: 100,
        runtime: None,
        codex_home: "fixture".into(),
        launcher: "fixture".into(),
        account_fingerprint: "fixture".into(),
        models: models
            .iter()
            .map(|m| ModelAvailability {
                id: m.id.clone(),
                discovered: true,
                supported_efforts: m.efforts.clone(),
                verified_efforts: m.efforts.clone(),
                verified_at: Some(100),
            })
            .collect(),
    };
    (policy, models, availability)
}

#[test]
fn stronger_recommendation_keeps_inherited_pair_without_task_qualification() {
    let (policy, models, availability) = fixture();
    let advice = choose_assessed(
        &policy,
        CapabilityFloor::Frontier,
        "protected",
        &models,
        &availability,
        100,
    )
    .unwrap();
    assert_eq!(advice, ("gpt-6-astra".into(), "high".into()));
    // No Sol task qualification row exists: that cannot veto advisory execution.
    assert!(models[0].qualifications.is_empty());
    let actual =
        advisory_pair("gpt-6.1-sol", "xhigh", &policy, &models, &availability, 100).unwrap();
    assert_eq!(actual, ("gpt-6.1-sol".into(), "xhigh".into()));
    assert_ne!(advice, actual);
}

#[test]
fn stronger_effort_recommendation_does_not_change_selected_effort() {
    let (policy, mut models, availability) = fixture();
    models[0].qualifications.push(Qualification {
        effort: "high".into(),
        envelope: "normal".into(),
        status: QualificationStatus::Qualified,
        floor: CapabilityFloor::Workhorse,
        preference_rank: 1,
    });
    assert_eq!(
        choose_assessed(
            &policy,
            CapabilityFloor::Workhorse,
            "normal",
            &models,
            &availability,
            100
        )
        .unwrap()
        .1,
        "high"
    );
    assert_eq!(
        advisory_pair("gpt-6.1-sol", "low", &policy, &models, &availability, 100)
            .unwrap()
            .1,
        "low"
    );
}

#[test]
fn explicit_owner_exclusion_still_blocks_selected_model() {
    let (mut policy, models, availability) = fixture();
    policy.denied_models.push("gpt-6.1-sol".into());
    assert!(
        advisory_pair("gpt-6.1-sol", "high", &policy, &models, &availability, 100)
            .unwrap_err()
            .contains("excluded")
    );
}

#[test]
fn explicit_owner_floor_is_distinct_from_assessed_floor() {
    let (mut policy, models, availability) = fixture();
    policy.floor = CapabilityFloor::Frontier;
    assert!(
        advisory_pair("gpt-6.1-sol", "high", &policy, &models, &availability, 100)
            .unwrap_err()
            .contains("explicit capability floor")
    );
    policy.floor = CapabilityFloor::Workhorse;
    assert!(advisory_pair("gpt-6.1-sol", "high", &policy, &models, &availability, 100).is_ok());
}

#[test]
fn unreleased_or_unknown_worker_still_cannot_launch() {
    let (policy, mut models, availability) = fixture();
    assert!(advisory_pair("unknown", "high", &policy, &models, &availability, 100).is_err());
    models[0].released = false;
    assert!(advisory_pair("gpt-6.1-sol", "high", &policy, &models, &availability, 100).is_err());
}

#[test]
fn availability_and_effort_evidence_remain_required() {
    let (policy, models, availability) = fixture();
    for change in 0..7 {
        let mut evidence = availability.clone();
        match change {
            0 => evidence.models.clear(),
            1 => evidence.models[0].verified_efforts.clear(),
            2 => evidence.models[0].supported_efforts.clear(),
            3 => evidence.models[0].verified_at = None,
            4 => evidence.observed_at = 101,
            5 => evidence.models[0].verified_at = Some(101),
            _ => evidence.observed_at = -100_000,
        }
        assert!(
            advisory_pair("gpt-6.1-sol", "high", &policy, &models, &evidence, 100).is_err(),
            "case {change}"
        );
    }
    assert!(
        advisory_pair(
            "gpt-6.1-sol",
            "unsupported",
            &policy,
            &models,
            &availability,
            100
        )
        .is_err()
    );
}

#[test]
fn auto_still_requires_task_qualification_and_cannot_use_advisory_gate() {
    let (mut policy, models, availability) = fixture();
    policy.mode = RoutingMode::Auto;
    assert!(advisory_pair("gpt-6.1-sol", "high", &policy, &models, &availability, 100).is_err());
    assert_eq!(
        choose_assessed(
            &policy,
            CapabilityFloor::Frontier,
            "protected",
            &models,
            &availability,
            100
        )
        .unwrap()
        .0,
        "gpt-6-astra"
    );
    policy.denied_models.push("gpt-6-astra".into());
    assert!(
        choose_assessed(
            &policy,
            CapabilityFloor::Frontier,
            "protected",
            &models,
            &availability,
            100
        )
        .is_err()
    );
    policy.mode = RoutingMode::Manual;
    assert!(advisory_pair("gpt-6.1-sol", "high", &policy, &models, &availability, 100).is_err());
}

#[test]
fn advisory_floor_increase_is_not_execution_escalation_but_failure_is_guarded() {
    assert!(!escalation_requires_consent(
        RoutingMode::Shadow,
        false,
        true
    ));
    assert!(escalation_requires_consent(RoutingMode::Auto, false, true));
    for mode in [RoutingMode::Shadow, RoutingMode::Auto] {
        assert!(escalation_requires_consent(mode, true, false));
        assert!(escalation_requires_consent(mode, true, true));
    }
}

#[test]
fn repository_scope_and_independent_work_restrictions_still_apply() {
    let root = std::env::current_dir().unwrap();
    let mut task = Assignment {
        task: "review".into(),
        message: "Review the specified source".into(),
        context: "Read only".into(),
        paths: vec!["crates".into()],
        independent: true,
        size: "batch".into(),
        read_only: true,
    };
    task.validate(&root).unwrap();
    for path in ["../outside", "/etc", "crates/../../outside"] {
        task.paths = vec![path.into()];
        assert!(task.validate(&root).is_err());
    }
    task.paths = vec!["crates".into()];
    task.independent = false;
    assert!(task.validate(&root).is_err());
    task.independent = true;
    task.context = "x".repeat(4001);
    assert!(task.validate(&root).is_err());
    let mut child = task.clone();
    child.paths = vec!["crates/executors".into()];
    assert!(task.overlaps(&child));
    child.paths = vec!["docs".into()];
    assert!(!task.overlaps(&child));
}

#[test]
fn shadow_brief_keeps_only_explicit_floor_while_recommendation_stays_separate() {
    let (mut policy, _, _) = fixture();
    assert_eq!(
        instruction_floor(&policy, CapabilityFloor::Frontier),
        CapabilityFloor::Assessed
    );
    policy.floor = CapabilityFloor::Workhorse;
    assert_eq!(
        instruction_floor(&policy, CapabilityFloor::Frontier),
        CapabilityFloor::Workhorse
    );
    policy.mode = RoutingMode::Auto;
    assert_eq!(
        instruction_floor(&policy, CapabilityFloor::Frontier),
        CapabilityFloor::Frontier
    );
}

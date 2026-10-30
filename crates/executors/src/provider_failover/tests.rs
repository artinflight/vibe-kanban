use std::sync::atomic::{AtomicUsize, Ordering};

use super::*;
static SEQ: AtomicUsize = AtomicUsize::new(0);
struct Fixture {
    root: PathBuf,
}
impl Fixture {
    fn new() -> Self {
        let base =
            std::env::var_os("VK_FAILOVER_TEST_ROOT").expect("private SSD test root required");
        let root = PathBuf::from(base).join(format!(
            "case-{}-{}",
            std::process::id(),
            SEQ.fetch_add(1, Ordering::Relaxed)
        ));
        let mut builder = fs::DirBuilder::new();
        #[cfg(unix)]
        {
            use std::os::unix::fs::DirBuilderExt;
            builder.mode(0o700);
        }
        builder.create(&root).unwrap();
        Self { root }
    }
    fn controller(&self) -> Controller {
        let mut c = Controller::create(&self.root).unwrap();
        c.observe_pool(pool("openai", Provider::Codex, 'a'))
            .unwrap();
        c.observe_pool(pool("anthropic", Provider::Claude, 'b'))
            .unwrap();
        let mut ag = pool("google", Provider::Antigravity, 'c');
        ag.authorized = false;
        ag.adapter_verified = false;
        c.observe_pool(ag).unwrap();
        c.register(work()).unwrap();
        c
    }
}
fn pool(id: &str, provider: Provider, ch: char) -> Pool {
    Pool {
        identity: Identity {
            provider,
            pool_id: id.into(),
            binding_key: format!("sha256:{}", ch.to_string().repeat(64)),
        },
        generation: "generation-1".into(),
        allocation_rank: Some(match id {
            "openai" => 1,
            "anthropic" => 2,
            _ => 3,
        }),
        source_receipt: "synthetic:pool-1".into(),
        observed_at_ms: 1000,
        valid_until_ms: 1_000_000,
        windows_complete: true,
        windows: vec![
            Window {
                id: "short".into(),
                kind: "provider_short_window".into(),
                available: Some(true),
                reset_at_ms: Some(50_000),
            },
            Window {
                id: "week".into(),
                kind: "provider_weekly_window".into(),
                available: Some(true),
                reset_at_ms: Some(900_000),
            },
        ],
        authorized: true,
        adapter_verified: true,
        handoff_supported: true,
        auth_verified_at_ms: Some(1000),
        health_verified_at_ms: Some(1000),
    }
}
fn candidate(id: &str) -> Candidate {
    Candidate {
        pool_id: id.into(),
        model: format!("synthetic-{id}"),
        effort: "high".into(),
        service_tier: "standard".into(),
        scope_key: "scope-protected".into(),
        qualification_version: "qualification-v1".into(),
        qualified: true,
        rank: 1,
    }
}
fn work() -> Work {
    Work {
        id: "work-1".into(),
        workspace_id: "workspace-1".into(),
        objective: "Finish the approved change".into(),
        execution_id: "exec-1".into(),
        incumbent: candidate("openai"),
        policy: Policy {
            mode: Mode::Auto,
            failover_authorized: true,
            scope_key: "scope-protected".into(),
            qualification_version: "qualification-v1".into(),
            locked: None,
            excluded_models: vec![],
            candidates: vec![candidate("google"), candidate("anthropic")],
        },
        native_goal_active: false,
        event: None,
        checkpoint: None,
        phase: Phase::Watching,
        attempts: 0,
        launch_receipt: None,
        effects: BTreeMap::new(),
    }
}
fn event() -> LimitEvent {
    LimitEvent {
        id: "limit-1".into(),
        execution_id: "exec-1".into(),
        identity: pool("openai", Provider::Codex, 'a').identity,
        source_receipt: "synthetic:native-quota-event".into(),
        observed_at_ms: 2000,
        failure: Failure::Quota {
            window_id: "short".into(),
        },
        retry_at_ms: Some(60_000),
    }
}
fn checkpoint() -> Checkpoint {
    Checkpoint {
        execution_id: "exec-1".into(),
        objective: work().objective,
        context: "Use the existing approved design; review the current files.".into(),
        workspace_id: "workspace-1".into(),
        workspace_path: "/synthetic/workspace".into(),
        branch: "feature/example".into(),
        workspace_snapshot: "sha256:head-index-dirty-untracked".into(),
        completed_steps: vec!["edit-one".into()],
        pending_steps: vec!["run-focused-test".into()],
        pending_approvals: vec![],
        effects: vec![
            Effect {
                id: "edit-one".into(),
                outcome: EffectOutcome::Completed,
                receipt: "synthetic:file-receipt".into(),
            },
            Effect {
                id: "run-focused-test".into(),
                outcome: EffectOutcome::NotStarted,
                receipt: "synthetic:fenced-not-started".into(),
            },
        ],
        all_workers_terminal: true,
        terminal_receipt: "synthetic:process-tree-reaped".into(),
        effects_complete: true,
        failed_validation: false,
        native_thread_id: Some("codex-thread".into()),
        native_turn_id: Some("codex-turn".into()),
    }
}
fn ready(c: &mut Controller) {
    c.observe("work-1", event()).unwrap();
    c.checkpoint("work-1", checkpoint()).unwrap();
}
fn permit() -> Admission {
    Admission {
        receipt: "synthetic:admission".into(),
        work_id: "work-1".into(),
        transition_id: "transition-1".into(),
        execution_id: "exec-2".into(),
        identity: pool("anthropic", Provider::Claude, 'b').identity,
        generation: "generation-1".into(),
        scope_key: "scope-protected".into(),
        qualification_version: "qualification-v1".into(),
        candidate: candidate("anthropic"),
        observed_at_ms: 2500,
        valid_until_ms: 4000,
        global_lane_granted: true,
        budget_granted: true,
    }
}
fn boundary() -> Boundary {
    Boundary {
        work_id: "work-1".into(),
        previous_execution_id: "exec-1".into(),
        workspace_id: "workspace-1".into(),
        workspace_snapshot: checkpoint().workspace_snapshot,
        terminal_receipt: checkpoint().terminal_receipt,
        ownership_fence: "synthetic:exclusive-owner".into(),
        all_workers_terminal: true,
        effects_reconciled: true,
        observed_at_ms: 2500,
        valid_until_ms: 4000,
    }
}
fn launch() -> LaunchReceipt {
    LaunchReceipt {
        source_receipt: "synthetic:native-launch".into(),
        transition_id: "transition-1".into(),
        execution_id: "exec-2".into(),
        identity: pool("anthropic", Provider::Claude, 'b').identity,
        effective: candidate("anthropic"),
        native_session_id: "claude-session".into(),
        native_turn_id: None,
    }
}
fn is_hold(plan: Plan, reason: &str) {
    assert!(
        matches!(plan,Plan::Hold{reason:r,..} if r==reason),
        "{plan:?}"
    );
}

#[test]
fn synthetic_mid_task_quota_handoff_preserves_dirty_state_and_does_not_repeat_effects() {
    let f = Fixture::new();
    let mut c = f.controller();
    let file = f.root.join("dirty-work.txt");
    fs::write(&file, "uncommitted useful work").unwrap();
    ready(&mut c);
    assert_eq!(c.plan("work-1", 3000), Plan::Ready(candidate("anthropic")));
    let t = c.claim("work-1", permit(), boundary(), 3000).unwrap();
    // Fake adapter consumes actual persisted handoff; no real provider/worker.
    assert_eq!(t.previous_execution_id, "exec-1");
    assert_eq!(t.identity.provider, Provider::Claude);
    assert_eq!(fs::read_to_string(file).unwrap(), "uncommitted useful work");
    c.confirm_started("work-1", launch()).unwrap();
    assert!(!c.claim_effect("work-1", "edit-one").unwrap());
    assert!(c.claim_effect("work-1", "run-focused-test").unwrap());
    let effect_file = f.root.join("fake-effect-count");
    fs::write(&effect_file, "1").unwrap();
    // Simulate a crash after the external effect but before its completion receipt.
    drop(c);
    let mut c = Controller::open(&f.root).unwrap();
    assert!(c.claim_effect("work-1", "run-focused-test").is_err());
    c.confirm_effect(
        "work-1",
        "run-focused-test",
        "synthetic:verified-effect-once",
    )
    .unwrap();
    assert!(!c.claim_effect("work-1", "run-focused-test").unwrap());
    assert_eq!(fs::read_to_string(effect_file).unwrap(), "1");
    assert!(c.claim_effect("work-1", "invented-new-effect").is_err());
    assert!(c.claim("work-1", permit(), boundary(), 3001).is_err());
}
#[test]
fn running_or_ambiguous_previous_outcome_never_switches() {
    let f = Fixture::new();
    let mut c = f.controller();
    c.observe("work-1", event()).unwrap();
    is_hold(c.plan("work-1", 3000), "checkpoint_required");
    let mut cp = checkpoint();
    cp.all_workers_terminal = false;
    c.checkpoint("work-1", cp).unwrap();
    is_hold(c.plan("work-1", 3000), "prior_worker_outcome_unknown");
    let mut cp = checkpoint();
    cp.effects[0].outcome = EffectOutcome::Unknown;
    c.checkpoint("work-1", cp).unwrap();
    is_hold(c.plan("work-1", 3000), "side_effect_outcome_unknown");
}
#[test]
fn duplicate_limit_is_idempotent_and_conflicting_identity_rejected() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let revision = c.state.revision;
    c.observe("work-1", event()).unwrap();
    assert_eq!(revision, c.state.revision);
    let mut conflict = event();
    conflict.retry_at_ms = Some(100_000);
    assert!(c.observe("work-1", conflict).is_err());
    let t = c.claim("work-1", permit(), boundary(), 3000).unwrap();
    c.observe("work-1", event()).unwrap();
    assert_eq!(c.work("work-1").unwrap().phase, Phase::DispatchPending(t));
}
#[test]
fn reset_requires_covering_fresh_evidence_new_generation_and_all_windows() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let old = c.state.pools["openai"].clone();
    assert!(!c.pool_ready(&old, 950_000));
    let mut p = old.clone();
    p.observed_at_ms = 60_000;
    assert!(!c.pool_ready(&p, 60_000));
    p.generation = "generation-2".into();
    assert!(c.pool_ready(&p, 60_000));
    p.windows[1].available = Some(false);
    assert!(!c.pool_ready(&p, 60_000));
    p.windows[1].available = None;
    assert!(!c.pool_ready(&p, 60_000));
    p.windows[1].available = Some(true);
    p.observed_at_ms = 59_999;
    assert!(!c.pool_ready(&p, 60_000));
    p.observed_at_ms = 60_000;
    p.valid_until_ms = 60_000;
    assert!(!c.pool_ready(&p, 60_000));
}
#[test]
fn retry_after_seconds_and_server_date_are_wait_hints_not_permission() {
    assert_eq!(
        retry_deadline(RetryAfter::Seconds(120), 1000),
        Some(121_000)
    );
    assert_eq!(
        retry_deadline(
            RetryAfter::ServerDate {
                date_ms: 900_000,
                server_now_ms: 700_000
            },
            1000
        ),
        Some(201_000)
    );
    assert_eq!(retry_deadline(RetryAfter::Seconds(u64::MAX), 1000), None);
    let f = Fixture::new();
    let mut c = f.controller();
    let mut e = event();
    e.failure = Failure::RateLimit;
    e.retry_at_ms = Some(201_000);
    c.observe("work-1", e).unwrap();
    let mut p = c.state.pools["openai"].clone();
    assert!(!c.pool_ready(&p, 201_000));
    p.observed_at_ms = 200_999;
    assert!(!c.pool_ready(&p, 201_000));
    p.observed_at_ms = 201_000;
    assert!(c.pool_ready(&p, 201_000));
}
#[test]
fn unavailable_auth_failed_and_exhausted_providers_hold_without_paid_fallback() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let mut p = c.state.pools["anthropic"].clone();
    p.authorized = false;
    p.observed_at_ms = 2000;
    c.observe_pool(p.clone()).unwrap();
    is_hold(c.plan("work-1", 3000), "no_authorized_qualified_provider");
    p.authorized = true;
    p.observed_at_ms = 2100;
    p.windows[0].available = Some(false);
    c.observe_pool(p.clone()).unwrap();
    is_hold(c.plan("work-1", 3000), "no_authorized_qualified_provider");
    p.windows[0].available = Some(true);
    p.observed_at_ms = 2200;
    c.observe_pool(p).unwrap();
    let mut auth = event();
    auth.failure = Failure::Authentication;
    c.observe(
        "work-1",
        LimitEvent {
            id: "auth-old".into(),
            ..auth
        },
    )
    .unwrap();
    let mut p = c.state.pools["openai"].clone();
    p.observed_at_ms = 100_000;
    p.generation = "generation-2".into();
    assert!(!c.pool_ready(&p, 100_000));
    p.auth_verified_at_ms = Some(100_000);
    assert!(c.pool_ready(&p, 100_000));
    let t = c.claim("work-1", permit(), boundary(), 3000).unwrap();
    c.confirm_started("work-1", launch()).unwrap();
    c.observe(
        "work-1",
        LimitEvent {
            id: "auth-new".into(),
            execution_id: t.execution_id,
            identity: t.identity,
            source_receipt: "synthetic:auth".into(),
            observed_at_ms: 3100,
            failure: Failure::Authentication,
            retry_at_ms: None,
        },
    )
    .unwrap();
    is_hold(c.plan("work-1", 3200), "alternate_attempt_exhausted");
}
#[test]
fn interrupted_handoff_reopens_without_launch_replay_or_parallel_owner() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    assert!(Controller::open(&f.root).is_err());
    let t = c.claim("work-1", permit(), boundary(), 3000).unwrap();
    drop(c);
    let mut c = Controller::open(&f.root).unwrap();
    assert_eq!(c.work("work-1").unwrap().phase, Phase::DispatchPending(t));
    is_hold(c.plan("work-1", 3001), "dispatch_outcome_unknown");
    assert!(c.claim("work-1", permit(), boundary(), 3001).is_err());
    let mut wrong = launch();
    wrong.execution_id = "wrong-execution".into();
    assert!(c.confirm_started("work-1", wrong).is_err());
    c.confirm_started("work-1", launch()).unwrap();
    c.confirm_started("work-1", launch()).unwrap();
    assert_eq!(c.work("work-1").unwrap().attempts, 1);
}
#[test]
fn interrupted_pre_dispatch_recovers_same_checkpoint_and_reserves_once() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    drop(c);
    let mut c = Controller::open(&f.root).unwrap();
    assert_eq!(c.work("work-1").unwrap().checkpoint, Some(checkpoint()));
    c.claim("work-1", permit(), boundary(), 3000).unwrap();
    assert!(c.claim("work-1", permit(), boundary(), 3001).is_err());
}
#[test]
fn recommend_manual_model_lock_and_qualification_never_grant_launch() {
    for case in 0..6 {
        let f = Fixture::new();
        let mut c = f.controller();
        ready(&mut c);
        let w = c.state.works.get_mut("work-1").unwrap();
        match case {
            0 => w.policy.mode = Mode::Recommend,
            1 => w.policy.mode = Mode::Manual,
            2 => w.policy.locked = Some(w.incumbent.clone()),
            3 => w
                .policy
                .candidates
                .iter_mut()
                .for_each(|c| c.qualified = false),
            4 => w.policy.qualification_version = "new-version".into(),
            _ => w.policy.excluded_models.push(candidate("anthropic").model),
        }
        if case == 0 {
            assert_eq!(
                c.plan("work-1", 3000),
                Plan::Recommend(candidate("anthropic"))
            );
        } else {
            assert!(matches!(c.plan("work-1", 3000), Plan::Hold { .. }));
        }
        assert!(c.claim("work-1", permit(), boundary(), 3000).is_err());
    }
}
#[test]
fn pending_approval_failed_validation_and_native_goal_preserve_protection() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let mut cp = checkpoint();
    cp.pending_approvals = vec!["approval-1".into()];
    c.checkpoint("work-1", cp.clone()).unwrap();
    is_hold(c.plan("work-1", 3000), "pending_approval");
    drop(c);
    let mut c = Controller::open(&f.root).unwrap();
    assert_eq!(c.work("work-1").unwrap().checkpoint, Some(cp));
    let mut cp = checkpoint();
    cp.failed_validation = true;
    c.checkpoint("work-1", cp).unwrap();
    is_hold(c.plan("work-1", 3000), "failed_validation_protection");
    c.state.works.get_mut("work-1").unwrap().native_goal_active = true;
    is_hold(c.plan("work-1", 3000), "native_goal_owner_pinned");
}
#[test]
fn identity_alias_rebinding_unknown_windows_and_stale_observations_rejected() {
    let f = Fixture::new();
    let mut c = f.controller();
    let p = c.state.pools["openai"].clone();
    let mut alias = p.clone();
    alias.identity.pool_id = "second-profile".into();
    assert!(c.observe_pool(alias).is_err());
    let mut other = p.clone();
    other.identity.binding_key = format!("sha256:{}", "d".repeat(64));
    assert!(c.observe_pool(other).is_err());
    let mut stale = p.clone();
    stale.observed_at_ms = 999;
    assert!(c.observe_pool(stale).is_err());
    let mut e = event();
    e.failure = Failure::Quota {
        window_id: "invented-five-hour".into(),
    };
    assert!(c.observe("work-1", e).is_err());
    let mut incomplete = p;
    incomplete.windows_complete = false;
    assert!(!c.pool_ready(&incomplete, 3000));
}
#[test]
fn auth_outage_task_failure_and_unknown_are_not_quota_exhaustion() {
    for failure in [
        Failure::Authentication,
        Failure::Outage,
        Failure::TaskFailure,
        Failure::Unknown,
    ] {
        let f = Fixture::new();
        let mut c = f.controller();
        let mut e = event();
        e.failure = failure.clone();
        c.observe("work-1", e).unwrap();
        c.checkpoint("work-1", checkpoint()).unwrap();
        if matches!(failure, Failure::TaskFailure | Failure::Unknown) {
            is_hold(c.plan("work-1", 3000), "task_failure_requires_review");
            assert!(c.state.blocks.is_empty());
        } else {
            assert_eq!(c.plan("work-1", 3000), Plan::Ready(candidate("anthropic")));
            assert_ne!(
                c.state.blocks["openai"][0].event.failure,
                Failure::Quota {
                    window_id: "short".into()
                }
            );
        }
    }
}
#[test]
fn admission_capacity_budget_expiry_scope_and_dirty_state_are_rechecked() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    for i in 0..7 {
        let mut p = permit();
        match i {
            0 => p.global_lane_granted = false,
            1 => p.budget_granted = false,
            2 => p.valid_until_ms = 3000,
            3 => p.generation = "changed".into(),
            4 => p.scope_key = "changed".into(),
            5 => p.candidate.effort = "low".into(),
            _ => p.identity.binding_key = "wrong-account".into(),
        };
        assert!(c.claim("work-1", p, boundary(), 3000).is_err());
    }
    assert!(
        c.claim(
            "work-1",
            permit(),
            Boundary {
                workspace_snapshot: "different-dirty-state".into(),
                ..boundary()
            },
            3000
        )
        .is_err()
    );
    assert_eq!(c.work("work-1").unwrap().attempts, 0);
}
#[test]
fn journal_failure_cannot_release_dispatch_and_corrupt_or_missing_state_cannot_reset() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    // Simulate interrupted/failed staging write without filling host disk.
    fs::create_dir(f.root.join(format!(
        ".state-{}-{}.next",
        std::process::id(),
        c.state.revision + 1
    )))
    .unwrap();
    assert!(c.claim("work-1", permit(), boundary(), 3000).is_err());
    is_hold(c.plan("work-1", 3000), "journal_recovery_required");
    drop(c);
    let c = Controller::open(&f.root).unwrap();
    assert_eq!(c.work("work-1").unwrap().attempts, 0);
    drop(c);
    fs::write(f.root.join("state.json"), b"truncated").unwrap();
    assert!(Controller::open(&f.root).is_err());
    assert!(Controller::create(&f.root).is_err());
    fs::remove_file(f.root.join("state.json")).unwrap();
    assert!(Controller::open(&f.root).is_err());
    assert!(Controller::create(&f.root).is_err());
}

#[test]
fn bounded_refresh_backoff_never_overrides_retry_after() {
    assert_eq!(refresh_deadline(0, 1000, None), Some(6000));
    assert_eq!(refresh_deadline(4, 1000, Some(90_000)), Some(90_000));
    assert_eq!(refresh_deadline(5, 1000, None), None);
    assert_eq!(refresh_deadline(0, u64::MAX, None), None);
}
#[test]
fn reset_cannot_omit_the_exhausted_window_or_reopen_on_clock_rollback() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let mut p = c.state.pools["openai"].clone();
    p.generation = "new".into();
    p.observed_at_ms = 60_000;
    p.windows.retain(|w| w.id != "short");
    assert!(!c.pool_ready(&p, 60_000));
    is_hold(c.plan("work-1", 1999), "clock_reconciliation_required");
}
#[test]
fn native_actual_model_and_receipt_conflicts_hold() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    c.claim("work-1", permit(), boundary(), 3000).unwrap();
    let mut wrong = launch();
    wrong.effective.model = "other-model".into();
    assert!(c.confirm_started("work-1", wrong).is_err());
    is_hold(c.plan("work-1", 3000), "dispatch_outcome_unknown");
    c.confirm_started("work-1", launch()).unwrap();
    let mut conflict = launch();
    conflict.native_session_id = "other".into();
    assert!(c.confirm_started("work-1", conflict).is_err());
    drop(c);
    let c = Controller::open(&f.root).unwrap();
    assert_eq!(c.work("work-1").unwrap().launch_receipt, Some(launch()));
}

#[test]
fn boundary_fence_expiry_and_new_worker_stop_transfer() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    for b in [
        Boundary {
            all_workers_terminal: false,
            ..boundary()
        },
        Boundary {
            ownership_fence: String::new(),
            ..boundary()
        },
        Boundary {
            valid_until_ms: 3000,
            ..boundary()
        },
        Boundary {
            effects_reconciled: false,
            ..boundary()
        },
        Boundary {
            previous_execution_id: "changed".into(),
            ..boundary()
        },
    ] {
        assert!(c.claim("work-1", permit(), b, 3000).is_err());
    }
    assert_eq!(c.work("work-1").unwrap().attempts, 0);
}
#[test]
fn unknown_auth_and_unverified_antigravity_are_not_routing_candidates() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let mut p = c.state.pools["anthropic"].clone();
    p.auth_verified_at_ms = None;
    p.observed_at_ms = 2200;
    c.observe_pool(p).unwrap();
    is_hold(c.plan("work-1", 3000), "no_authorized_qualified_provider");
}

#[test]
fn allocation_ranks_do_not_price_or_compare_provider_allowances() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    let mut p = c.pool("google").unwrap().clone();
    p.authorized = true;
    p.adapter_verified = true;
    p.allocation_rank = Some(1);
    p.observed_at_ms = 2200;
    c.observe_pool(p).unwrap();
    assert_eq!(c.plan("work-1", 3000), Plan::Ready(candidate("anthropic")));
    // A preference rank cannot open Antigravity, or turn unknown measurement
    // into more usable capacity than an eligible measured provider.
    let mut p = c.pool("anthropic").unwrap().clone();
    p.allocation_rank = None;
    p.observed_at_ms = 2300;
    c.observe_pool(p).unwrap();
    assert_eq!(c.plan("work-1", 3000), Plan::Ready(candidate("anthropic")));
}

fn codex_quota() -> native::Signal {
    native::codex("account/rateLimits/updated", &serde_json::json!({"rateLimits": {
        "limitId":"coding", "primary":{"usedPercent":100,"windowDurationMins":180,"resetsAt":50},
        "secondary":{"usedPercent":35,"windowDurationMins":10080,"resetsAt":900}
    }})).unwrap().unwrap()
}
fn native_end(execution: &str, now: u64, quiet: bool, preserved: bool) -> observer::Ended {
    observer::Ended {
        execution_id: execution.into(),
        source_receipt: "synthetic:exit".into(),
        observed_at_ms: now,
        exit_code: Some(1),
        process_group_quiescent: quiet,
        preservation_verified: preserved,
    }
}
#[test]
fn native_codex_preserves_distinct_sourced_windows_and_no_assumed_five_hours() {
    let signal = codex_quota();
    assert_eq!(signal.windows[0].kind, "minutes:180");
    assert_eq!(signal.windows[0].reset_at_ms, Some(50_000));
    assert_eq!(signal.windows[0].available, Some(false));
    assert_eq!(signal.windows[1].available, Some(true));
    assert_eq!(signal.windows[1].id, "codex:coding:secondary");
    let s = native::codex(
        "account/rateLimits/updated",
        &serde_json::json!({"rateLimits":{
        "primary":{"usedPercent":10}}}),
    )
    .unwrap()
    .unwrap();
    assert_eq!(s.windows[0].kind, "unknown_duration");
    assert_eq!(s.windows[0].reset_at_ms, None);
}
#[test]
fn native_codex_structured_failure_classification_never_uses_error_prose() {
    for (info, failure) in [
        (
            serde_json::json!("usageLimitExceeded"),
            Failure::QuotaUnspecified,
        ),
        (serde_json::json!("unauthorized"), Failure::Authentication),
        (serde_json::json!("serverOverloaded"), Failure::Outage),
        (
            serde_json::json!({"httpConnectionFailed":{"httpStatusCode":429}}),
            Failure::RateLimit,
        ),
        (
            serde_json::json!({"responseStreamDisconnected":{"httpStatusCode":503}}),
            Failure::Outage,
        ),
        (
            serde_json::json!("contextWindowExceeded"),
            Failure::TaskFailure,
        ),
        (serde_json::json!("other"), Failure::Unknown),
    ] {
        let s = native::codex("error", &serde_json::json!({"threadId":"thread", "turnId":"turn", "willRetry":true,
            "error":{"message":"quota exhausted; secret-looking prose ignored", "codexErrorInfo":info}})).unwrap().unwrap();
        assert_eq!(s.failure, Some(failure));
        assert_eq!(s.native_retrying, Some(true));
        assert!(
            !serde_json::to_string(&s)
                .unwrap()
                .contains("secret-looking")
        );
    }
}
#[test]
fn native_claude_rejected_and_warning_preserve_window_specific_resets() {
    for (status, available) in [
        ("allowed", true),
        ("allowed_warning", true),
        ("rejected", false),
    ] {
        let s = native::claude(&serde_json::json!({"type":"rate_limit_event", "session_id":"claude-native", "rate_limit_info":{
            "status":status,"rateLimitType":"seven_day_sonnet","resetsAt":900,"utilization":0.9,
            "overageStatus":"allowed", "private_extra":"not retained"}})).unwrap().unwrap();
        assert_eq!(s.windows[0].id, "claude:seven_day_sonnet");
        assert_eq!(s.windows[0].reset_at_ms, Some(900_000));
        assert_eq!(s.windows[0].available, Some(available));
        assert_eq!(s.failure.is_some(), !available);
        assert!(!serde_json::to_string(&s).unwrap().contains("private_extra"));
    }
}
#[test]
fn native_unknown_schema_and_overflow_fail_closed_without_credential_inspection() {
    assert!(
        native::claude(
            &serde_json::json!({"type":"rate_limit_event","session_id":"s","rate_limit_info":{
        "status":"rejected","rateLimitType":"future_window"}})
        )
        .is_err()
    );
    assert!(
        native::claude(&serde_json::json!({"type":"rate_limit_event","rate_limit_info":{}}))
            .is_err()
    );
    assert!(
        native::codex(
            "account/rateLimits/updated",
            &serde_json::json!({"rateLimits":{"primary":{
        "usedPercent":100,"resetsAt":u64::MAX}}})
        )
        .is_err()
    );
    assert!(
        native::codex(
            "account/rateLimits/updated",
            &serde_json::json!({"rateLimits":{"primary":{
        "usedPercent":-1}}})
        )
        .is_err()
    );
    assert!(
        native::codex(
            "item/completed",
            &serde_json::json!({"message":"rate limit"})
        )
        .unwrap()
        .is_none()
    );
}
#[test]
fn native_limit_and_journal_are_atomic_duplicates_do_not_extend_cooldown() {
    let f = Fixture::new();
    let mut c = f.controller();
    let identity = pool("openai", Provider::Codex, 'a').identity;
    c.record_native(
        "work-1",
        "exec-1",
        &identity,
        codex_quota(),
        "synthetic:native",
        2000,
    )
    .unwrap();
    let before = c.state.clone();
    c.record_native(
        "work-1",
        "exec-1",
        &identity,
        codex_quota(),
        "synthetic:duplicate",
        2100,
    )
    .unwrap();
    assert_eq!(c.state, before);
    assert_eq!(c.state.blocks["openai"].len(), 1);
    assert_eq!(
        c.work("work-1").unwrap().event.as_ref().unwrap().failure,
        Failure::Quota {
            window_id: "codex:coding:primary".into()
        }
    );
    drop(c);
    let c = Controller::open(&f.root).unwrap();
    assert_eq!(c.state, before);
}
#[test]
fn native_retry_or_parent_exit_is_not_a_safe_lifecycle_checkpoint() {
    for (quiet, preserved, ready) in [
        (false, true, false),
        (true, false, false),
        (true, true, true),
    ] {
        let f = Fixture::new();
        let mut c = f.controller();
        c.record_native(
            "work-1",
            "exec-1",
            &pool("openai", Provider::Codex, 'a').identity,
            codex_quota(),
            "synthetic:native",
            2000,
        )
        .unwrap();
        c.checkpoint("work-1", checkpoint()).unwrap();
        is_hold(c.plan("work-1", 3000), "native_lifecycle_not_fenced");
        c.record_ended(native_end("exec-1", 2500, quiet, preserved))
            .unwrap();
        if ready {
            assert_eq!(c.plan("work-1", 3000), Plan::Ready(candidate("anthropic")));
        } else {
            is_hold(c.plan("work-1", 3000), "native_lifecycle_not_fenced");
        }
    }
}
#[test]
fn native_allowed_signal_and_passed_reset_clock_do_not_re_admit_pool() {
    let f = Fixture::new();
    let mut c = f.controller();
    let id = pool("openai", Provider::Codex, 'a').identity;
    c.record_native(
        "work-1",
        "exec-1",
        &id,
        codex_quota(),
        "synthetic:native",
        2000,
    )
    .unwrap();
    let mut allowed = codex_quota();
    allowed.windows[0].available = Some(true);
    c.record_native(
        "work-1",
        "exec-1",
        &id,
        allowed,
        "synthetic:allowed",
        60_000,
    )
    .unwrap();
    assert!(!c.pool_ready(&c.state.pools["openai"], 60_000));
    let mut p = c.state.pools["openai"].clone();
    p.observed_at_ms = 60_001;
    c.observe_pool(p.clone()).unwrap();
    assert!(!c.pool_ready(&p, 60_002));
    p.generation = "verified-generation-2".into();
    p.observed_at_ms = 60_003;
    c.observe_pool(p.clone()).unwrap();
    // Complete/new generation alone cannot omit a newly discovered native bucket.
    assert!(!c.pool_ready(&p, 60_004));
    p.windows.push(Window {
        id: "codex:coding:primary".into(),
        kind: "minutes:180".into(),
        available: Some(true),
        reset_at_ms: Some(230_000),
    });
    p.observed_at_ms = 60_005;
    c.observe_pool(p.clone()).unwrap();
    assert!(c.pool_ready(&p, 60_006));
}
#[test]
fn native_no_auto_astra_even_without_exclusion_or_when_alternate_is_unavailable() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut w = c.work("work-1").unwrap().clone();
    w.policy.candidates.retain(|v| v.pool_id == "anthropic");
    w.policy.candidates[0].model = "gpt-6-astra".into();
    c.state.works.insert(w.id.clone(), w);
    ready(&mut c);
    is_hold(c.plan("work-1", 3000), "no_authorized_qualified_provider");
    assert!(c.claim("work-1", permit(), boundary(), 3000).is_err());
}
#[test]
fn observer_is_dormant_without_host_binding_and_cannot_register_antigravity() {
    assert!(!observer::is_registered("unbound-execution"));
    assert!(!observer::codex("unbound-execution", "error", &serde_json::json!({})).unwrap());
    assert!(!observer::ended("unbound-execution", Some(1), true, true).unwrap());
    let f = Fixture::new();
    let c = std::sync::Arc::new(std::sync::Mutex::new(f.controller()));
    assert!(
        observer::register(
            &c,
            "work-1",
            "exec-1",
            pool("google", Provider::Antigravity, 'c').identity,
            "s",
            None
        )
        .is_err()
    );
}
#[test]
fn observer_binds_native_account_session_and_exclusive_execution_without_dispatch() {
    let f = Fixture::new();
    let mut c = f.controller();
    let wall = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64;
    for p in c.state.pools.values_mut() {
        p.observed_at_ms = wall - 1000;
        p.valid_until_ms = wall + 1_000_000;
    }
    let c = std::sync::Arc::new(std::sync::Mutex::new(c));
    let identity = pool("openai", Provider::Codex, 'a').identity;
    let registration = observer::register(
        &c,
        "work-1",
        "exec-1",
        identity.clone(),
        "native-thread",
        Some("coding".into()),
    )
    .unwrap();
    assert!(observer::register(&c, "work-1", "exec-1", identity, "native-thread", None).is_err());
    assert!(
        observer::codex(
            "exec-1",
            "error",
            &serde_json::json!({"threadId":"native-thread","turnId":"turn-1","willRetry":true,
        "error":{"codexErrorInfo":"usageLimitExceeded"}})
        )
        .unwrap()
    );
    {
        let c = c.lock().unwrap();
        assert_eq!(c.work("work-1").unwrap().phase, Phase::Watching);
        assert_eq!(c.state.native_records.len(), 1);
    }
    // A different session must not be attributed to this execution; durable hold.
    assert!(
        observer::codex(
            "exec-1",
            "error",
            &serde_json::json!({"threadId":"other-thread","turnId":"turn","willRetry":false,
        "error":{"codexErrorInfo":"usageLimitExceeded"}})
        )
        .is_err()
    );
    {
        let c = c.lock().unwrap();
        is_hold(
            c.plan("work-1", wall + 10),
            "native_adapter_reconciliation_required",
        );
    }
    drop(registration);
    assert!(!observer::is_registered("exec-1"));
}
#[test]
fn observer_malformed_bucket_durably_holds_instead_of_granting_capacity() {
    let f = Fixture::new();
    let c = std::sync::Arc::new(std::sync::Mutex::new(f.controller()));
    let _registration = observer::register(
        &c,
        "work-1",
        "exec-1",
        pool("openai", Provider::Codex, 'a').identity,
        "thread",
        Some("coding".into()),
    )
    .unwrap();
    assert!(
        observer::codex(
            "exec-1",
            "account/rateLimits/updated",
            &serde_json::json!({"rateLimits":{
        "limitId":"different-account-bucket","primary":{"usedPercent":0}}})
        )
        .is_err()
    );
    let c = c.lock().unwrap();
    assert!(c.state.native_records.is_empty());
    is_hold(
        c.plan("work-1", 3000),
        "native_adapter_reconciliation_required",
    );
}
#[test]
fn return_to_sol_requires_verified_reset_and_new_quiescent_alternate_checkpoint() {
    let f = Fixture::new();
    let mut c = f.controller();
    c.state.works.get_mut("work-1").unwrap().incumbent.model = "gpt-6.1-sol".into();
    ready(&mut c);
    c.claim("work-1", permit(), boundary(), 3000).unwrap();
    c.confirm_started("work-1", launch()).unwrap();
    let mut cp = checkpoint();
    cp.execution_id = "exec-2".into();
    cp.workspace_snapshot = "synthetic:current-dirty-state".into();
    is_hold(
        c.preferred_return("work-1", &cp, 60_000),
        "boundary_checkpoint_required",
    );
    let mut p = c.state.pools["openai"].clone();
    p.generation = "reset-verified".into();
    p.observed_at_ms = 60_001;
    c.observe_pool(p).unwrap();
    is_hold(
        c.preferred_return("work-1", &cp, 60_002),
        "boundary_checkpoint_required",
    );
    let mut ended = native_end("exec-2", 60_003, true, true);
    ended.exit_code = Some(0);
    c.record_ended(ended).unwrap();
    assert!(
        matches!(c.preferred_return("work-1",&cp,60_004),Plan::Recommend(v) if v.model=="gpt-6.1-sol")
    );
    assert!(c.claim("work-1", permit(), boundary(), 60_004).is_err());
    cp.failed_validation = true;
    is_hold(
        c.preferred_return("work-1", &cp, 60_005),
        "boundary_checkpoint_required",
    );
}

#[test]
fn observer_claude_native_session_is_bound_and_never_grants_billing_or_auth() {
    let f = Fixture::new();
    let mut controller = f.controller();
    let w = controller.state.works.get_mut("work-1").unwrap();
    w.incumbent = candidate("anthropic");
    let c = std::sync::Arc::new(std::sync::Mutex::new(controller));
    let _binding = observer::register(
        &c,
        "work-1",
        "exec-1",
        pool("anthropic", Provider::Claude, 'b').identity,
        "claude-native",
        None,
    )
    .unwrap();
    assert!(observer::claude("exec-1",&serde_json::json!({"type":"rate_limit_event","session_id":"claude-native","rate_limit_info":{
        "status":"rejected","rateLimitType":"five_hour","resetsAt":1900000000}})).unwrap());
    {
        let c = c.lock().unwrap();
        assert_eq!(c.state.native_records.len(), 1);
        assert_eq!(c.state.pools["anthropic"].auth_verified_at_ms, Some(1000));
        assert_eq!(
            c.state.pools["anthropic"].source_receipt,
            "synthetic:pool-1"
        );
        assert!(!c.pool_ready(&c.state.pools["anthropic"], 1_900_000_000_001));
    }
    assert!(observer::claude("exec-1",&serde_json::json!({"type":"rate_limit_event","session_id":"other-native","rate_limit_info":{
        "status":"allowed","rateLimitType":"five_hour"}})).is_err());
    assert!(c.lock().unwrap().state.adapter_holds.contains_key("exec-1"));
}
#[test]
fn native_storage_failure_cannot_persist_half_observation_or_release_dispatch() {
    let f = Fixture::new();
    let mut c = f.controller();
    let before = c.state.clone();
    fs::rename(f.root.join("state.json"), f.root.join("saved-state.json")).unwrap();
    fs::create_dir(f.root.join("state.json")).unwrap();
    assert!(
        c.record_native(
            "work-1",
            "exec-1",
            &pool("openai", Provider::Codex, 'a').identity,
            codex_quota(),
            "synthetic:native",
            2000
        )
        .is_err()
    );
    assert_eq!(c.state, before);
    is_hold(c.plan("work-1", 3000), "journal_recovery_required");
}

fn claude_login() -> claude::NativeLogin {
    claude::NativeLogin {
        identity: pool("anthropic", Provider::Claude, 'b').identity,
        source_receipt: "synthetic:native-auth-status".into(),
        launcher_digest: "synthetic:official-cli-pin".into(),
        os_user: "fixture-user".into(),
        logged_in: true,
        auth_method: "claude.ai".into(),
        subscription_type: "pro".into(),
        api_provider: "firstParty".into(),
        observed_at_ms: 1000,
        valid_until_ms: 10000,
    }
}
fn claude_trial() -> claude::Trial {
    claude::Trial {
        identity: claude_login().identity,
        launcher_digest: claude_login().launcher_digest,
        source_receipt: "synthetic:approved-native-trial".into(),
        model: claude::MODEL.into(),
        effort: claude::EFFORT.into(),
        supervised: true,
        approved_reads: true,
        exit_code: 0,
        limit_or_extra_usage_prompt: false,
    }
}
fn claude_profile() -> claude::ProfileFacts {
    claude::ProfileFacts {
        named_variant: claude::PROFILE.into(),
        official_claude: true,
        supervised: true,
        plan: false,
        bypass: false,
        router: false,
        disable_api_key: true,
        command_overrides: false,
        model: Some(claude::MODEL.into()),
        effort: Some(claude::EFFORT.into()),
        agent_override: false,
    }
}
#[test]
fn claude_verified_native_login_and_trial_enable_consideration_not_remaining_allowance() {
    let login = claude_login();
    claude::consideration(
        &login,
        &claude_trial(),
        &login.identity,
        &login.launcher_digest,
        "fixture-user",
        2000,
    )
    .unwrap();
    let mut p = pool("anthropic", Provider::Claude, 'b');
    p.windows[0].id = "claude:five_hour".into();
    p.windows[0].kind = "five_hour".into();
    p.windows[1].id = "claude:seven_day".into();
    p.windows[1].kind = "seven_day".into();
    p.windows_complete = false;
    assert!(claude::pool_allowed(&p, &login, 2000).is_err());
    p.windows_complete = true;
    p.windows[0].available = None;
    assert!(claude::pool_allowed(&p, &login, 2000).is_err());
    p.windows[0].available = Some(true);
    claude::pool_allowed(&p, &login, 2000).unwrap();
    p.windows.push(Window {
        id: "claude:overage".into(),
        kind: "overage".into(),
        available: Some(true),
        reset_at_ms: None,
    });
    assert!(claude::pool_allowed(&p, &login, 2000).is_err());
}
#[test]
fn claude_login_wrong_account_launcher_expiry_api_or_failed_trial_cannot_grant_eligibility() {
    for change in 0..6 {
        let mut login = claude_login();
        let mut trial = claude_trial();
        match change {
            0 => login.auth_method = "api-key".into(),
            1 => login.api_provider = "thirdParty".into(),
            2 => login.identity.pool_id = "other".into(),
            3 => login.launcher_digest = "changed-runtime".into(),
            4 => login.valid_until_ms = 1500,
            _ => trial.limit_or_extra_usage_prompt = true,
        }
        assert!(
            claude::consideration(
                &login,
                &trial,
                &claude_login().identity,
                &claude_login().launcher_digest,
                "fixture-user",
                2000
            )
            .is_err()
        );
    }
}
#[test]
fn claude_profile_requires_effective_supervision_not_a_magic_variant_label() {
    claude::validate_profile(&claude_profile()).unwrap();
    let mut default = claude_profile();
    default.named_variant = "DEFAULT".into();
    claude::validate_profile(&default).unwrap();
    for change in 0..8 {
        let mut p = claude_profile();
        match change {
            0 => p.plan = true,
            1 => p.bypass = true,
            2 => p.router = true,
            3 => p.command_overrides = true,
            4 => p.supervised = false,
            5 => p.disable_api_key = false,
            6 => p.agent_override = true,
            _ => p.model = Some("unqualified-model".into()),
        }
        assert!(claude::validate_profile(&p).is_err());
    }
}
#[test]
fn claude_subscription_route_rejects_override_names_without_reading_or_replacing_values() {
    claude::subscription_environment(["PATH", "VK_EXECUTION_PROCESS_ID", "HOME"]).unwrap();
    for name in [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "https_proxy",
        "CLAUDE_CODE_USE_VERTEX",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CONFIG_DIR",
        "api_key_helper",
        "CLAUDE_CODE_OAUTH_TOKEN",
    ] {
        assert!(claude::subscription_environment([name]).is_err());
    }
}
#[test]
fn claude_read_trial_never_qualifies_writes_or_higher_risk_by_itself() {
    let mut c = candidate("anthropic");
    c.model = claude::MODEL.into();
    c.effort = claude::EFFORT.into();
    claude::candidate_allowed(&c, true).unwrap();
    assert!(claude::candidate_allowed(&c, false).is_err());
    c.effort = "high".into();
    assert!(claude::candidate_allowed(&c, true).is_err());
    for tool in [
        "Write",
        "Edit",
        "Bash",
        "Task",
        "Agent",
        "WebFetch",
        "mcp__anything",
        "AskUserQuestion",
        "ExitPlanMode",
    ] {
        assert!(!claude::read_tool(tool));
    }
    assert!(claude::read_tool("Read"));
}
#[test]
fn claude_handoff_contains_task_delta_and_effect_receipts_not_cross_provider_resume_ids() {
    let c = checkpoint();
    let prompt = claude::handoff_prompt(&c).unwrap();
    assert!(prompt.contains(&c.objective));
    assert!(prompt.contains("edit-one"));
    assert!(!prompt.contains("codex-thread"));
    assert!(!prompt.contains("codex-turn"));
    assert!(!prompt.contains("--resume"));
    let with_actions = claude::handoff_prompt_with_actions(&c, &action_scope()).unwrap();
    assert!(with_actions.contains("approved-test-only"));
    assert!(with_actions.contains("run-focused-test"));
    assert!(!with_actions.contains("codex-thread"));
    let mut blocked = c.clone();
    blocked.pending_approvals.push("unapproved-action".into());
    assert!(claude::handoff_prompt(&blocked).is_err());
    blocked = c;
    blocked.context = "x".repeat(33000);
    assert!(claude::handoff_prompt(&blocked).is_err());
}
#[test]
fn fresh_claude_native_binding_fences_all_tools_until_verified_model_then_requires_read_only() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut child = candidate("anthropic");
    child.model = claude::MODEL.into();
    child.effort = claude::EFFORT.into();
    c.state.works.get_mut("work-1").unwrap().policy.candidates = vec![child.clone()];
    ready(&mut c);
    let mut p = permit();
    p.candidate = child;
    c.claim("work-1", p, boundary(), 3000).unwrap();
    let c = std::sync::Arc::new(std::sync::Mutex::new(c));
    let observer = observer::register_initial_claude(
        &c,
        "work-1",
        "exec-2",
        claude_login().identity,
        "synthetic:profile-pin",
    )
    .unwrap();
    assert!(!observer::tool_allowed("exec-2", "Read").unwrap());
    observer::verify_profile_pin("exec-2", "synthetic:profile-pin").unwrap();
    assert!(observer::verify_profile_pin("exec-2", "changed-profile").is_err());
    observer::claude("exec-2",&serde_json::json!({"type":"system","subtype":"init","session_id":"fresh-claude-native","model":claude::MODEL})).unwrap();
    assert!(observer::tool_allowed("exec-2", "Read").unwrap());
    assert!(!observer::tool_allowed("exec-2", "Task").unwrap());
    assert!(!observer::tool_allowed("exec-2", "Bash").unwrap());
    // No fabricated native effort/launch binding; an unknown receipt cannot be retried.
    assert!(matches!(
        c.lock().unwrap().work("work-1").unwrap().phase,
        Phase::DispatchPending(_)
    ));
    observer.retain_until_terminal();
    assert!(observer::read_only_handoff("exec-2").unwrap());
    observer::ended("exec-2", Some(0), true, true).unwrap();
    assert!(!observer::is_registered("exec-2"));
}
#[test]
fn fresh_claude_wrong_native_model_cannot_clear_hold_or_enable_tools() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut child = candidate("anthropic");
    child.model = claude::MODEL.into();
    child.effort = claude::EFFORT.into();
    c.state.works.get_mut("work-1").unwrap().policy.candidates = vec![child.clone()];
    ready(&mut c);
    let mut p = permit();
    p.candidate = child;
    c.claim("work-1", p, boundary(), 3000).unwrap();
    let c = std::sync::Arc::new(std::sync::Mutex::new(c));
    let _observer = observer::register_initial_claude(
        &c,
        "work-1",
        "exec-2",
        claude_login().identity,
        "synthetic:profile-pin",
    )
    .unwrap();
    assert!(observer::claude("exec-2",&serde_json::json!({"type":"system","subtype":"init","session_id":"fresh-native","model":"wrong-model"})).is_err());
    assert!(!observer::tool_allowed("exec-2", "Read").unwrap());
}

#[test]
fn claude_handoff_hook_covers_reads_and_delegation_instead_of_ordinary_exclusions() {
    let ordinary = serde_json::json!({"Stop":[{"hookCallbackIds":["existing-stop"]}],"PreToolUse":[{"matcher":"^(?!(Read|Task)$).*"}]});
    let guarded = claude::handoff_hooks(Some(ordinary.clone()));
    assert_eq!(guarded["Stop"], ordinary["Stop"]);
    assert_eq!(guarded["PreToolUse"][0]["matcher"], ".*");
    assert_eq!(
        guarded["PreToolUse"][0]["hookCallbackIds"][0],
        "provider_read_approval"
    );
}

#[test]
fn claude_login_does_not_certify_startup_effects_or_permission_to_spend_paid_extra() {
    let login = claude_login();
    let mut proof = claude::LaunchSafety {
        identity: login.identity.clone(),
        source_receipt: "synthetic:settings-review".into(),
        launcher_digest: login.launcher_digest.clone(),
        profile_digest: "profile-pin".into(),
        workspace_snapshot: "snapshot-pin".into(),
        surface_digest: "nonsecret-settings-and-startup-surface-pin".into(),
        no_unfenced_startup_effects: false,
        paid_extra_disabled: false,
        observed_at_ms: 1000,
        valid_until_ms: 10000,
    };
    assert!(claude::launch_safety(&proof, &login, "profile-pin", "snapshot-pin", 2000).is_err());
    proof.no_unfenced_startup_effects = true;
    assert!(claude::launch_safety(&proof, &login, "profile-pin", "snapshot-pin", 2000).is_err());
    proof.paid_extra_disabled = true;
    claude::launch_safety(&proof, &login, "profile-pin", "snapshot-pin", 2000).unwrap();
    assert!(
        claude::launch_safety(&proof, &login, "profile-pin", "changed-snapshot", 2000).is_err()
    );
}

#[test]
fn claude_actual_native_effort_is_persisted_and_required_for_native_launch_confirmation() {
    for effort in ["low", "high"] {
        let f = Fixture::new();
        let mut c = f.controller();
        let mut child = candidate("anthropic");
        child.model = claude::MODEL.into();
        child.effort = claude::EFFORT.into();
        c.state.works.get_mut("work-1").unwrap().policy.candidates = vec![child.clone()];
        ready(&mut c);
        let mut p = permit();
        p.candidate = child;
        c.claim("work-1", p, boundary(), 3000).unwrap();
        let c = std::sync::Arc::new(std::sync::Mutex::new(c));
        let _guard = observer::register_initial_claude(
            &c,
            "work-1",
            "exec-2",
            claude_login().identity,
            "synthetic:profile-pin",
        )
        .unwrap();
        let result = observer::claude(
            "exec-2",
            &serde_json::json!({"type":"system","subtype":"init",
            "session_id":"new-native-session","model":claude::MODEL,"effort":effort}),
        );
        if effort == "low" {
            result.unwrap();
            let c = c.lock().unwrap();
            assert!(matches!(c.work("work-1").unwrap().phase, Phase::Running(_)));
            let fact = c.state.native_records.values().last().unwrap();
            assert_eq!(fact.signal.native_model.as_deref(), Some(claude::MODEL));
            assert_eq!(fact.signal.native_effort.as_deref(), Some("low"));
        } else {
            assert!(result.is_err());
            assert!(!observer::tool_allowed("exec-2", "Read").unwrap());
        }
    }
}

fn capacity(
    c: &Controller,
    candidate: Candidate,
    remaining: u64,
    observed: u64,
) -> selection::Capacity {
    let p = c.pool(&candidate.pool_id).unwrap();
    selection::Capacity {
        candidate,
        generation: p.generation.clone(),
        source_receipt: "synthetic:capacity".into(),
        calibration_receipt: "synthetic:accepted-work-measurement".into(),
        reference_work: "bounded-reference-task-v1".into(),
        calibration_version: "measured-v1".into(),
        sample_count: 3,
        remaining_work: remaining,
        applicable_windows: p.windows.iter().map(|w| w.id.clone()).collect(),
        economical: true,
        cost_constraint_receipt: "synthetic:approved-native-no-extras".into(),
        observed_at_ms: observed,
        valid_until_ms: 900_000,
    }
}
fn alternate_stopped(c: &mut Controller) -> Checkpoint {
    c.state.works.get_mut("work-1").unwrap().incumbent.model = "gpt-6.1-sol".into();
    ready(c);
    c.claim("work-1", permit(), boundary(), 3000).unwrap();
    c.confirm_started("work-1", launch()).unwrap();
    let mut cp = checkpoint();
    cp.execution_id = "exec-2".into();
    cp.workspace_snapshot = "synthetic:new-dirty-checkpoint".into();
    let mut ended = native_end("exec-2", 60_003, true, true);
    ended.exit_code = Some(0);
    c.record_ended(ended).unwrap();
    let mut p = c.pool("openai").unwrap().clone();
    p.generation = "observed-reset".into();
    p.observed_at_ms = 60_004;
    c.observe_pool(p).unwrap();
    cp
}
#[test]
fn measured_headroom_precedes_sol_preference_and_reset_never_interrupts_worker() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    let sol = c.work("work-1").unwrap().incumbent.clone();
    c.observe_capacity(capacity(&c, sol.clone(), 2, 60_005))
        .unwrap();
    c.observe_capacity(capacity(&c, candidate("anthropic"), 8, 60_005))
        .unwrap();
    assert_eq!(
        c.boundary_plan("work-1", &cp, 60_006),
        Plan::Ready(candidate("anthropic"))
    );
    let mut running = cp.clone();
    running.all_workers_terminal = false;
    is_hold(
        c.boundary_plan("work-1", &running, 60_006),
        "boundary_checkpoint_required",
    );
    c.observe_capacity(capacity(&c, sol.clone(), 12, 60_007))
        .unwrap();
    assert_eq!(c.boundary_plan("work-1", &cp, 60_008), Plan::Ready(sol));
}
#[test]
fn unknown_stale_or_unusable_capacity_cannot_outrank_fresh_measurement() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    let sol = c.work("work-1").unwrap().incumbent.clone();
    c.observe_capacity(capacity(&c, candidate("anthropic"), 2, 60_005))
        .unwrap();
    assert_eq!(
        c.boundary_plan("work-1", &cp, 60_006),
        Plan::Ready(candidate("anthropic"))
    );
    let mut expired = capacity(&c, sol.clone(), 999, 60_005);
    expired.valid_until_ms = 60_006;
    c.observe_capacity(expired).unwrap();
    assert_eq!(
        c.boundary_plan("work-1", &cp, 60_007),
        Plan::Ready(candidate("anthropic"))
    );
    let mut costly = capacity(&c, candidate("anthropic"), 20, 60_008);
    costly.economical = false;
    c.observe_capacity(costly).unwrap();
    assert_eq!(c.boundary_plan("work-1", &cp, 60_009), Plan::Ready(sol));
}
#[test]
fn incompatible_capacity_units_incomplete_windows_and_generation_do_not_compare() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    let sol = c.work("work-1").unwrap().incumbent.clone();
    c.observe_capacity(capacity(&c, sol, 2, 60_005)).unwrap();
    let mut v = capacity(&c, candidate("anthropic"), 8, 60_005);
    v.reference_work = "different-task-not-a-percentage".into();
    c.observe_capacity(v.clone()).unwrap();
    is_hold(
        c.boundary_plan("work-1", &cp, 60_006),
        "capacity_measurements_incomparable",
    );
    v.observed_at_ms = 60_007;
    v.applicable_windows.pop();
    assert!(c.observe_capacity(v.clone()).is_err());
    v.applicable_windows.push("week".into());
    v.generation = "guessed-reset".into();
    assert!(c.observe_capacity(v).is_err());
}
#[test]
fn sol_is_default_on_unknown_or_equal_capacity_but_never_overrides_manual_constraints() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    let sol = c.work("work-1").unwrap().incumbent.clone();
    assert_eq!(
        c.boundary_plan("work-1", &cp, 60_005),
        Plan::Ready(sol.clone())
    );
    c.observe_capacity(capacity(&c, sol.clone(), 4, 60_005))
        .unwrap();
    c.observe_capacity(capacity(&c, candidate("anthropic"), 4, 60_005))
        .unwrap();
    assert_eq!(c.boundary_plan("work-1", &cp, 60_006), Plan::Ready(sol));
    c.state.works.get_mut("work-1").unwrap().policy.locked = Some(candidate("anthropic"));
    assert_eq!(
        c.boundary_plan("work-1", &cp, 60_006),
        Plan::Ready(candidate("anthropic"))
    );
    c.state.works.get_mut("work-1").unwrap().policy.mode = Mode::Recommend;
    assert_eq!(
        c.boundary_plan("work-1", &cp, 60_006),
        Plan::Recommend(candidate("anthropic"))
    );
    c.state.works.get_mut("work-1").unwrap().policy.mode = Mode::Manual;
    is_hold(
        c.boundary_plan("work-1", &cp, 60_006),
        "manual_or_goal_owner_pinned",
    );
}
#[test]
fn boundary_claim_recovers_exact_ids_retains_initial_usage_and_never_bounces() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    // Old journal shape retained the observed transfer/launch only on Work.
    c.state.transfers.clear();
    c.state.launches.clear();
    let sol = c.work("work-1").unwrap().incumbent.clone();
    let mut p = permit();
    p.transition_id = "return-2".into();
    p.execution_id = "exec-3".into();
    p.candidate = sol.clone();
    p.identity = c.pool("openai").unwrap().identity.clone();
    p.generation = "observed-reset".into();
    p.observed_at_ms = 60_005;
    p.valid_until_ms = 70_000;
    let mut b = boundary();
    b.previous_execution_id = "exec-2".into();
    b.workspace_snapshot = cp.workspace_snapshot.clone();
    b.observed_at_ms = 60_005;
    b.valid_until_ms = 70_000;
    let mut changed = p.clone();
    changed.transition_id = "transition-1".into();
    assert!(
        c.claim_boundary("work-1", cp.clone(), changed, b.clone(), 60_006)
            .is_err()
    );
    let t = c
        .claim_boundary("work-1", cp.clone(), p, b, 60_006)
        .unwrap();
    assert_eq!(t.previous_execution_id, "exec-2");
    assert_eq!(
        c.transfer("transition-1").unwrap().previous_execution_id,
        "exec-1"
    );
    drop(c);
    let mut c = Controller::open(&f.root).unwrap();
    assert_eq!(c.transfer("return-2").unwrap(), &t);
    assert_eq!(c.state.launches.len(), 1);
    let receipt = LaunchReceipt {
        source_receipt: "synthetic:native-sol".into(),
        transition_id: t.transition_id,
        execution_id: t.execution_id,
        identity: t.identity,
        effective: t.candidate,
        native_session_id: "NEW-native-sol-not-claude-resume".into(),
        native_turn_id: None,
    };
    c.confirm_started("work-1", receipt.clone()).unwrap();
    c.confirm_started("work-1", receipt).unwrap();
    assert_eq!(c.state.launches.len(), 2);
    let mut reuse = work();
    reuse.id = "new-independent-work".into();
    reuse.workspace_id = "different-workspace".into();
    reuse.execution_id = "exec-2".into();
    assert!(c.register(reuse).is_err());

    is_hold(
        c.boundary_plan("work-1", &cp, 60_007),
        "boundary_attempt_exhausted",
    );
}
fn readiness_scope() -> readiness::Scope {
    readiness::Scope {
        authority_contract: "synthetic-owner-contract-not-a-git-protocol".into(),
        workspace_id: "workspace-1".into(),
        execution_id: "exec-1".into(),
        snapshot_receipt: "synthetic:dirty".into(),
        repository_inventory: "inventory-v1".into(),
        head_inventory: "head-v1".into(),
        owner_generation: "owner-v1".into(),
        effective_permissions: "supervised-v1".into(),
        authorized_actions: "actions-v1".into(),
        toolchain: "toolchain-v1".into(),
        qualification_version: "qualification-v1".into(),
        catalog_version: "catalog-v1".into(),
    }
}
fn readiness_receipt() -> readiness::Receipt {
    readiness::Receipt {
        authority_contract: "synthetic-owner-contract-not-a-git-protocol".into(),
        source_receipt: "synthetic:ready".into(),
        scope: readiness_scope(),
        observed_at_ms: 2000,
        valid_until_ms: 4000,
        blockers: vec![],
        preservation_verified: true,
        exclusive_owner_verified: true,
    }
}
#[test]
fn readiness_missing_blocked_expired_future_or_failed_preservation_never_authorizes() {
    use readiness::{Readiness, check};
    let expected = readiness_scope();
    let r = readiness_receipt();
    assert!(matches!(
        check(Some(&r), &expected, 3000),
        Readiness::Ready { .. }
    ));
    assert_eq!(
        check(None, &expected, 3000),
        Readiness::Hold {
            reason: "readiness_authority_unavailable".into()
        }
    );
    for now in [1999, 4000, 5000] {
        assert!(matches!(
            check(Some(&r), &expected, now),
            Readiness::Hold { .. }
        ));
    }
    let mut bad = r.clone();
    bad.preservation_verified = false;
    assert!(matches!(
        check(Some(&bad), &expected, 3000),
        Readiness::Hold { .. }
    ));
    bad = r;
    bad.blockers.push("source_capture_pending".into());
    assert_eq!(
        check(Some(&bad), &expected, 3000),
        Readiness::Hold {
            reason: "readiness_blocked:source_capture_pending".into()
        }
    );
}
#[test]
fn readiness_reuse_invalidates_every_relevant_scope_dependency() {
    let r = readiness_receipt();
    let original = serde_json::to_value(readiness_scope()).unwrap();
    for key in original.as_object().unwrap().keys() {
        let mut changed = original.clone();
        changed[key] = "changed".into();
        let scope = serde_json::from_value(changed).unwrap();
        assert_eq!(
            readiness::check(Some(&r), &scope, 3000),
            readiness::Readiness::Hold {
                reason: "readiness_dependencies_changed".into()
            },
            "{key}"
        );
    }
}
#[test]
fn usage_fetch_throttle_is_bounded_metadata_backoff_not_generation_quota() {
    let f = Fixture::new();
    let c = f.controller();
    let fetch = readiness::UsageFetch {
        identity: c.pool("anthropic").unwrap().identity.clone(),
        source_receipt: "synthetic:usage-fetch-429".into(),
        observed_at_ms: 2000,
        retry_at_ms: Some(90_000),
        throttled: true,
    };
    for attempt in 0..5 {
        assert!(fetch.next_refresh(attempt, 3000).unwrap() >= 90_000);
    }
    assert_eq!(fetch.next_refresh(5, 3000), None);
    assert!(c.state.blocks.is_empty());
    assert!(c.work("work-1").unwrap().event.is_none());
}
fn action_scope() -> tools::Actions {
    tools::Actions {
        source_receipt: "synthetic:authorized-coding-qualified".into(),
        scope_key: "scope-protected".into(),
        qualification_version: "qualification-v1".into(),
        local_writes: true,
        effects: vec![tools::EffectGrant {
            effect_id: "run-focused-test".into(),
            tool: "Bash".into(),
            input: serde_json::json!({"command":"approved-test-only"}),
        }],
    }
}
#[test]
fn qualified_supervised_coding_can_write_but_external_actions_require_exact_grants() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut cp = checkpoint();
    cp.workspace_path = f.root.to_str().unwrap().into();
    c.observe("work-1", event()).unwrap();
    c.checkpoint("work-1", cp.clone()).unwrap();
    let mut b = boundary();
    b.workspace_snapshot = cp.workspace_snapshot.clone();
    c.claim("work-1", permit(), b, 3000).unwrap();
    c.authorize_actions("work-1", action_scope()).unwrap();
    let input =
        serde_json::json!({"file_path":f.root.join("new.rs"),"content":"authorized new source"});
    assert!(c.action_allowed("work-1", "exec-2", "Write", &input));
    assert!(!c.action_allowed(
        "work-1",
        "exec-2",
        "Write",
        &serde_json::json!({"file_path":"/outside/secret"})
    ));
    assert!(!c.action_allowed(
        "work-1",
        "exec-2",
        "Write",
        &serde_json::json!({"file_path":f.root.join("../escape")})
    ));
    c.claim_tool("work-1", "exec-2", "tool-write", "Write", &input)
        .unwrap();
    assert!(
        c.claim_tool("work-1", "exec-2", "tool-write", "Write", &input)
            .is_err()
    );
    c.complete_tool("work-1", "exec-2", "tool-write", "Write", &input)
        .unwrap();
    assert!(c.state.tool_uses["exec-2:tool-write"].completed);
    let bash = serde_json::json!({"command":"approved-test-only"});
    assert!(!c.action_allowed(
        "work-1",
        "exec-2",
        "Bash",
        &serde_json::json!({"command":"different-command"})
    ));
    c.claim_tool("work-1", "exec-2", "tool-bash", "Bash", &bash)
        .unwrap();
    assert_eq!(
        c.work("work-1").unwrap().effects["run-focused-test"].outcome,
        EffectOutcome::Unknown
    );
    assert!(
        c.claim_tool("work-1", "exec-2", "new-tool-id", "Bash", &bash)
            .is_err()
    );
    c.complete_tool("work-1", "exec-2", "tool-bash", "Bash", &bash)
        .unwrap();
    assert!(
        c.claim_tool("work-1", "exec-2", "another-tool-id", "Bash", &bash)
            .is_err()
    );
}
#[test]
fn partial_tool_reply_survives_reopen_and_blocks_provider_transition() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut cp = alternate_stopped(&mut c);
    // Actions normally installed while pending; this fixture stages the exact phase.
    let t = match c.work("work-1").unwrap().phase.clone() {
        Phase::Running(t) => t,
        _ => panic!(),
    };
    c.state.works.get_mut("work-1").unwrap().phase = Phase::DispatchPending(t);
    c.authorize_actions("work-1", action_scope()).unwrap();
    c.claim_tool(
        "work-1",
        "exec-2",
        "partial",
        "Bash",
        &serde_json::json!({"command":"approved-test-only"}),
    )
    .unwrap();
    drop(c);
    let c = Controller::open(&f.root).unwrap();
    is_hold(
        c.boundary_plan("work-1", &cp, 60_010),
        "boundary_checkpoint_required",
    );
    cp.effects
        .iter_mut()
        .find(|e| e.id == "run-focused-test")
        .unwrap()
        .outcome = EffectOutcome::Completed;
    is_hold(
        c.boundary_plan("work-1", &cp, 60_010),
        "boundary_checkpoint_required",
    );
}
#[test]
fn task_action_qualification_changes_are_rejected_without_permanent_read_only_rule() {
    let mut actions = action_scope();
    let cp = checkpoint();
    let candidate = candidate("anthropic");
    actions.validate(&candidate, &cp).unwrap();
    actions.qualification_version = "stale".into();
    assert!(actions.validate(&candidate, &cp).is_err());
    actions = action_scope();
    actions.effects[0].effect_id = "edit-one".into();
    assert!(actions.validate(&candidate, &cp).is_err());
    let mut c = candidate.clone();
    c.model = claude::MODEL.into();
    c.effort = claude::EFFORT.into();
    claude::candidate_allowed(&c, true).unwrap();
    assert!(claude::candidate_allowed(&c, false).is_err());
}
#[cfg(unix)]
#[test]
fn local_write_scope_rejects_symlink_escape() {
    let f = Fixture::new();
    let outside = Fixture::new();
    std::os::unix::fs::symlink(&outside.root, f.root.join("alias")).unwrap();
    let mut cp = checkpoint();
    cp.workspace_path = f.root.to_str().unwrap().into();
    assert!(!action_scope().allows(
        &cp,
        "Write",
        &serde_json::json!({"file_path":f.root.join("alias/escape.rs")})
    ));
}
#[test]
fn reported_claude_limit_and_ui_recovery_do_not_fabricate_window_type_timezone_or_capacity() {
    // Sanitized replay of supplied observations: native exit1 plus reported reset
    // is not a structured window. Later successful UI observations establish
    // observed recovery, not a quota API, complete inventory or measured headroom.
    let recorded = serde_json::json!({"type":"result","is_error":true,"session_id":"synthetic-native","result":"reported reset 17:20; window unknown"});
    assert!(native::claude(&recorded).unwrap().is_none());
    for (session, weekly) in [(0, 6), (14, 7)] {
        let ui = serde_json::json!({"source":"operator_ui_observation","session_used_percent":session,"weekly_used_percent":weekly,"extras_enabled":false,"timezone":null});
        assert!(ui["timezone"].is_null());
        let mut p = pool("anthropic", Provider::Claude, 'b');
        p.windows_complete = false;
        assert!(claude::pool_allowed(&p, &claude_login(), 2000).is_err());
    }
}
#[test]
fn ordinary_alternate_failure_and_unverified_start_hold_instead_of_provider_retry() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    c.state.ended.get_mut("exec-2").unwrap().exit_code = Some(1);
    is_hold(
        c.boundary_plan("work-1", &cp, 60_010),
        "task_failure_requires_review",
    );
    let mut e = event();
    e.id = "claude-genuine-quota".into();
    e.execution_id = "exec-2".into();
    e.identity = c.pool("anthropic").unwrap().identity.clone();
    e.observed_at_ms = 60_011;
    c.observe("work-1", e).unwrap();
    assert!(
        matches!(c.boundary_plan("work-1",&cp,60_012),Plan::Ready(v) if v.model=="gpt-6.1-sol")
    );
    c.state.works.get_mut("work-1").unwrap().launch_receipt = None;
    is_hold(
        c.boundary_plan("work-1", &cp, 60_012),
        "native_start_unverified",
    );
}
#[test]
fn explicit_terminal_effect_reconciliation_is_required_and_durable() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut cp = alternate_stopped(&mut c);
    let t = match c.work("work-1").unwrap().phase.clone() {
        Phase::Running(t) => t,
        _ => panic!(),
    };
    c.state.works.get_mut("work-1").unwrap().phase = Phase::DispatchPending(t);
    c.authorize_actions("work-1", action_scope()).unwrap();
    let input = serde_json::json!({"command":"approved-test-only"});
    c.claim_tool("work-1", "exec-2", "partial", "Bash", &input)
        .unwrap();
    let proof = tools::ReconciledTool {
        execution_id: "exec-2".into(),
        tool_use_id: "partial".into(),
        tool: "Bash".into(),
        input,
        outcome: EffectOutcome::Completed,
        source_receipt: "synthetic:independent-effect-reconciliation".into(),
    };
    let mut bad = proof.clone();
    bad.tool_use_id = "invented-successful-admission".into();
    assert!(c.reconcile_tool("work-1", bad).is_err());
    c.reconcile_tool("work-1", proof).unwrap();
    let e = c.work("work-1").unwrap().effects["run-focused-test"].clone();
    *cp.effects
        .iter_mut()
        .find(|e| e.id == "run-focused-test")
        .unwrap() = e;
    assert!(matches!(
        c.boundary_plan("work-1", &cp, 60_010),
        Plan::Ready(_)
    ));
    drop(c);
    let c = Controller::open(&f.root).unwrap();
    assert!(c.state.tool_uses["exec-2:partial"].completed);
}
#[test]
fn explicit_accepted_completion_releases_only_fully_reconciled_work_and_keeps_history() {
    let f = Fixture::new();
    let mut c = f.controller();
    let mut cp = alternate_stopped(&mut c);
    assert!(c.finish("work-1", &cp, "accepted-result").is_err());
    cp.pending_steps.clear();
    c.finish("work-1", &cp, "accepted-result").unwrap();
    c.finish("work-1", &cp, "accepted-result").unwrap();
    assert!(c.finish("work-1", &cp, "conflicting").is_err());
    is_hold(c.plan("work-1", 60_010), "work_completed");
    is_hold(c.boundary_plan("work-1", &cp, 60_010), "work_completed");
    assert!(c.transfer("transition-1").is_some());
    let mut next = work();
    next.id = "independent-work-2".into();
    next.execution_id = "exec-next-task".into();
    c.register(next).unwrap();
}
#[test]
fn durable_approved_effect_receipt_is_idempotent_but_cannot_change_outcome() {
    let f = Fixture::new();
    let mut c = f.controller();
    alternate_stopped(&mut c);
    let t = match c.work("work-1").unwrap().phase.clone() {
        Phase::Running(t) => t,
        _ => panic!(),
    };
    c.state.works.get_mut("work-1").unwrap().phase = Phase::DispatchPending(t);
    c.authorize_actions("work-1", action_scope()).unwrap();
    let input = serde_json::json!({"command":"approved-test-only"});
    c.claim_tool("work-1", "exec-2", "partial", "Bash", &input)
        .unwrap();
    let mut proof = tools::ReconciledTool {
        execution_id: "exec-2".into(),
        tool_use_id: "partial".into(),
        tool: "Bash".into(),
        input,
        outcome: EffectOutcome::NotStarted,
        source_receipt: "synthetic:verified-no-effect".into(),
    };
    c.reconcile_tool("work-1", proof.clone()).unwrap();
    c.reconcile_tool("work-1", proof.clone()).unwrap();
    proof.outcome = EffectOutcome::Completed;
    assert!(c.reconcile_tool("work-1", proof).is_err());
}
#[test]
fn native_codex_return_binds_new_thread_actual_settings_and_keeps_unreported_effort_unknown() {
    let f = Fixture::new();
    let mut c = f.controller();
    let cp = alternate_stopped(&mut c);
    let sol = c.work("work-1").unwrap().incumbent.clone();
    let mut p = permit();
    p.transition_id = "return-2".into();
    p.execution_id = "exec-3".into();
    p.candidate = sol;
    p.identity = c.pool("openai").unwrap().identity.clone();
    p.generation = "observed-reset".into();
    p.observed_at_ms = 60_005;
    p.valid_until_ms = 70_000;
    let mut b = boundary();
    b.previous_execution_id = "exec-2".into();
    b.workspace_snapshot = cp.workspace_snapshot.clone();
    b.observed_at_ms = 60_005;
    b.valid_until_ms = 70_000;
    c.claim_boundary("work-1", cp, p, b, 60_006).unwrap();
    let identity = c.pool("openai").unwrap().identity.clone();
    let c = std::sync::Arc::new(std::sync::Mutex::new(c));
    let _guard = observer::register_initial_codex(
        &c,
        "work-1",
        "exec-3",
        identity,
        "synthetic:exact-profile-pin",
    )
    .unwrap();
    observer::codex_started(
        "exec-3",
        "NEW-native-thread",
        "gpt-6.1-sol",
        None,
        "standard",
    )
    .unwrap();
    assert!(matches!(
        c.lock().unwrap().work("work-1").unwrap().phase,
        Phase::DispatchPending(_)
    ));
    assert!(
        c.lock()
            .unwrap()
            .state
            .native_records
            .values()
            .any(|r| r.execution_id == "exec-3"
                && r.signal.native_model.as_deref() == Some("gpt-6.1-sol")
                && r.signal.native_effort.is_none())
    );
    observer::codex_started(
        "exec-3",
        "NEW-native-thread",
        "gpt-6.1-sol",
        Some("high"),
        "standard",
    )
    .unwrap();
    assert!(matches!(
        c.lock().unwrap().work("work-1").unwrap().phase,
        Phase::Running(_)
    ));
    assert!(observer::verify_profile_pin("exec-3", "changed-profile").is_err());
}
#[test]
fn reconciled_not_started_cannot_ignore_late_contradictory_completion() {
    let f = Fixture::new();
    let mut c = f.controller();
    alternate_stopped(&mut c);
    let t = match c.work("work-1").unwrap().phase.clone() {
        Phase::Running(t) => t,
        _ => panic!(),
    };
    c.state.works.get_mut("work-1").unwrap().phase = Phase::DispatchPending(t);
    c.authorize_actions("work-1", action_scope()).unwrap();
    let input = serde_json::json!({"command":"approved-test-only"});
    c.claim_tool("work-1", "exec-2", "partial", "Bash", &input)
        .unwrap();
    c.reconcile_tool(
        "work-1",
        tools::ReconciledTool {
            execution_id: "exec-2".into(),
            tool_use_id: "partial".into(),
            tool: "Bash".into(),
            input: input.clone(),
            outcome: EffectOutcome::NotStarted,
            source_receipt: "synthetic:independently-not-started".into(),
        },
    )
    .unwrap();
    assert!(
        c.complete_tool("work-1", "exec-2", "partial", "Bash", &input)
            .is_err()
    );
}

fn bridge_native_end(c: &mut Controller, quiet: bool, preserved: bool) {
    let cp = checkpoint();
    let mut signal = codex_quota();
    signal.native_session_id = cp.native_thread_id;
    signal.native_turn_id = cp.native_turn_id;
    c.record_native(
        "work-1",
        "exec-1",
        &pool("openai", Provider::Codex, 'a').identity,
        signal,
        "synthetic:actual-native-fixture",
        2000,
    )
    .unwrap();
    c.record_ended(native_end("exec-1", 2500, quiet, preserved))
        .unwrap();
}
#[test]
fn trusted_bridge_parent_flags_without_native_and_exit_evidence_hold() {
    let f = Fixture::new();
    let c = f.controller();
    assert!(c.continuation_evidence("work-1", &checkpoint()).is_err());
}
#[test]
fn trusted_bridge_native_exit_or_preservation_uncertainty_holds() {
    for (quiet, preserved) in [(false, true), (true, false)] {
        let f = Fixture::new();
        let mut c = f.controller();
        bridge_native_end(&mut c, quiet, preserved);
        assert!(c.continuation_evidence("work-1", &checkpoint()).is_err());
    }
}
#[test]
fn trusted_bridge_durable_native_evidence_survives_reopen_without_minting_job_proof() {
    let f = Fixture::new();
    let mut c = f.controller();
    bridge_native_end(&mut c, true, true);
    let expected = c.continuation_evidence("work-1", &checkpoint()).unwrap();
    drop(c);
    let c = Controller::open(&f.root).unwrap();
    assert_eq!(
        expected,
        c.continuation_evidence("work-1", &checkpoint()).unwrap()
    );
}
#[test]
fn trusted_bridge_failed_validation_pending_approval_or_changed_native_hold() {
    let f = Fixture::new();
    let mut c = f.controller();
    bridge_native_end(&mut c, true, true);
    let mut cp = checkpoint();
    cp.failed_validation = true;
    assert!(c.continuation_evidence("work-1", &cp).is_err());
    cp.failed_validation = false;
    cp.pending_approvals
        .push("still requires permission".into());
    assert!(c.continuation_evidence("work-1", &cp).is_err());
    cp.pending_approvals.clear();
    let mut failed = event();
    failed.failure = Failure::TaskFailure;
    c.state.works.get_mut("work-1").unwrap().event = Some(failed);
    assert!(c.continuation_evidence("work-1", &cp).is_err());
    c.state.works.get_mut("work-1").unwrap().event = None;
    cp.native_thread_id = Some("wrong-provider-history".into());
    assert!(c.continuation_evidence("work-1", &cp).is_err());
}
#[test]
fn trusted_bridge_unfinished_native_tool_is_not_closed_by_checkpoint_flags() {
    let f = Fixture::new();
    let mut c = f.controller();
    bridge_native_end(&mut c, true, true);
    c.state.tool_uses.insert(
        "exec-1:late-tool".into(),
        tools::ToolUse {
            execution_id: "exec-1".into(),
            tool_use_id: "late-tool".into(),
            tool: "Edit".into(),
            input: serde_json::json!({"file_path":"/synthetic/source"}),
            effect_id: None,
            completed: false,
            reconciled_outcome: None,
            source_receipt: None,
        },
    );
    assert!(c.continuation_evidence("work-1", &checkpoint()).is_err());
}

#[test]
fn trusted_bridge_candidate_respects_qualification_lock_exclusion_and_goal_owner() {
    let f = Fixture::new();
    let mut c = f.controller();
    let chosen = candidate("anthropic");
    assert!(c.continuation_candidate("work-1", &chosen).is_ok());
    let mut changed = chosen.clone();
    changed.qualification_version = "not-qualified".into();
    assert!(c.continuation_candidate("work-1", &changed).is_err());
    c.state.works.get_mut("work-1").unwrap().policy.locked = Some(candidate("openai"));
    assert!(c.continuation_candidate("work-1", &chosen).is_err());
    c.state.works.get_mut("work-1").unwrap().policy.locked = None;
    c.state
        .works
        .get_mut("work-1")
        .unwrap()
        .policy
        .excluded_models
        .push(chosen.model.clone());
    assert!(c.continuation_candidate("work-1", &chosen).is_err());
    c.state
        .works
        .get_mut("work-1")
        .unwrap()
        .policy
        .excluded_models
        .clear();
    c.state.works.get_mut("work-1").unwrap().native_goal_active = true;
    assert!(c.continuation_candidate("work-1", &chosen).is_err());
}

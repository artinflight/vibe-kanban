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
fn allocation_rank_and_model_preference_are_separate_and_conflicts_hold() {
    let f = Fixture::new();
    let mut c = f.controller();
    ready(&mut c);
    // A fake verified third provider is legal ONLY inside this synthetic fixture.
    let mut p = c.state.pools["google"].clone();
    p.authorized = true;
    p.adapter_verified = true;
    p.observed_at_ms = 2200;
    p.allocation_rank = Some(1);
    c.observe_pool(p.clone()).unwrap();
    c.state.works.get_mut("work-1").unwrap().policy.candidates[0].rank = 99;
    let mut preferred = candidate("google");
    preferred.rank = 99;
    assert_eq!(c.plan("work-1", 3000), Plan::Ready(preferred));
    p.observed_at_ms = 2300;
    p.allocation_rank = Some(2);
    c.observe_pool(p).unwrap();
    is_hold(c.plan("work-1", 3000), "allocation_rank_conflict");
}

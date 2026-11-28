//! Opt-in local namespace acceptance. No Codex/native inference or production process.
#![cfg(target_os = "linux")]
use std::{fs, path::Path, process::Command, time::Instant};

use executors::{
    routing::{CapabilityFloor, RoutingMode, RoutingPolicy},
    routing_module::{self, Scope},
};
use sha2::{Digest, Sha256};

fn release(root: &Path, name: &str, worker: &Path, script: Option<&str>) {
    use std::os::unix::fs::PermissionsExt;
    let dir = root.join(name);
    fs::create_dir(&dir).unwrap();
    if let Some(script) = script {
        fs::write(dir.join("worker"), script).unwrap();
    } else {
        fs::copy(worker, dir.join("worker")).unwrap();
        assert!(
            Command::new("strip")
                .arg(dir.join("worker"))
                .status()
                .unwrap()
                .success()
        );
    }
    fs::set_permissions(dir.join("worker"), fs::Permissions::from_mode(0o555)).unwrap();
    fs::write(
        dir.join("models.json"),
        include_str!("../src/routing_models.json"),
    )
    .unwrap();
    if name == "b" {
        let mut policies: Vec<executors::routing::ModelPolicy> =
            serde_json::from_str(include_str!("../src/routing_models.json")).unwrap();
        for model in &mut policies {
            if model.id == "gpt-6-sol" {
                for q in &mut model.qualifications {
                    if q.envelope == "normal" && q.effort == "medium" {
                        q.preference_rank = 1;
                    }
                }
            }
        }
        fs::write(
            dir.join("models.json"),
            serde_json::to_vec(&policies).unwrap(),
        )
        .unwrap();
    }
    fs::write(
        dir.join("instructions.txt"),
        format!("Classification instructions {name}"),
    )
    .unwrap();
    let hash = |name| format!("{:x}", Sha256::digest(fs::read(dir.join(name)).unwrap()));
    fs::write(
        dir.join("manifest.json"),
        serde_json::to_vec(&routing_module::Manifest {
            protocol: routing_module::PROTOCOL,
            version: name.into(),
            worker_sha256: hash("worker"),
            models_sha256: hash("models.json"),
            instructions_sha256: hash("instructions.txt"),
            classifier_model: if name == "b" {
                "gpt-6-luna"
            } else {
                "gpt-5.6-luna"
            }
            .into(),
            classifier_effort: if name == "b" { "medium" } else { "low" }.into(),
        })
        .unwrap(),
    )
    .unwrap();
}
fn publish(root: &Path, name: &str) {
    let next = root.join("next");
    std::os::unix::fs::symlink(root.join(name), &next).unwrap();
    fs::rename(next, root.join("current")).unwrap();
}
fn assess(policy: &RoutingPolicy, prompt: &str) -> executors::routing_assessment::Assessment {
    routing_module::assess(
        prompt,
        None,
        None,
        None,
        None,
        false,
        policy,
        false,
        serde_json::Value::Null,
    )
    .0
}

fn routed(policy: &RoutingPolicy, prompt: &str) -> executors::actions::ExecutorAction {
    use executors::{
        actions::{
            ExecutorAction, ExecutorActionType, coding_agent_initial::CodingAgentInitialRequest,
        },
        executors::BaseCodingAgent,
        profile::ExecutorConfig,
    };
    let mut config = ExecutorConfig::new(BaseCodingAgent::Codex);
    config.model_id = Some("gpt-6-astra".into());
    config.reasoning_id = Some("high".into());
    config.routing = Some(Box::new(policy.clone()));
    let mut action = ExecutorAction::new(
        ExecutorActionType::CodingAgentInitialRequest(CodingAgentInitialRequest {
            prompt: prompt.into(),
            executor_config: config,
            working_dir: None,
        }),
        None,
    );
    executors::routing::resolve_action_with_context(&mut action, None, false, None).unwrap();
    action
}

fn captured_step(
    root: &Path,
    policy: &RoutingPolicy,
    prompt: &str,
    class: serde_json::Value,
) -> routing_module::Reply {
    let mut request = routing_module::Request {
        protocol: routing_module::PROTOCOL,
        stage: "before".into(),
        prompt: prompt.into(),
        previous_envelope: Some("protected".into()),
        completed_reply: Some("The design choice is settled; update the existing notes.".into()),
        failed: false,
        policy: policy.clone(),
        seed: (&executors::routing_assessment::assess(prompt)).into(),
        context: executors::routing_triage::repository_context(prompt, Some(root)),
        semantic: None,
    };
    request.seed = routing_module::verify_active_case(&request)
        .unwrap()
        .assessment;
    request.stage = "after".into();
    request.semantic = Some(class);
    routing_module::verify_active_case(&request).unwrap()
}

fn replay_completed_assessments(root: &Path, policy: &RoutingPolicy) {
    let Some(path) = std::env::var_os("VK_ROUTING_REPLAY_FILE") else {
        return;
    };
    let replay: serde_json::Value = serde_json::from_slice(&fs::read(path).unwrap()).unwrap();
    let availability: executors::routing::Availability =
        serde_json::from_value(replay["availability"].clone()).unwrap();
    let models: Vec<executors::routing::ModelPolicy> =
        serde_json::from_value(replay["models"].clone()).unwrap();
    for case in replay["cases"].as_array().unwrap() {
        let prompt = case["prompt"].as_str().unwrap();
        let mut request = routing_module::Request {
            protocol: routing_module::PROTOCOL,
            stage: "before".into(),
            prompt: prompt.into(),
            previous_envelope: case["previous_envelope"].as_str().map(str::to_owned),
            completed_reply: case["completed_reply"].as_str().map(str::to_owned),
            failed: false,
            policy: policy.clone(),
            seed: (&executors::routing_assessment::assess(prompt)).into(),
            context: executors::routing_triage::repository_context(prompt, Some(root)),
            semantic: None,
        };
        request.seed = routing_module::verify_active_case(&request)
            .unwrap()
            .assessment;
        request.stage = "after".into();
        request.semantic = case.get("semantic").filter(|c| !c.is_null()).cloned();
        let result = routing_module::verify_active_case(&request)
            .unwrap()
            .assessment;
        assert_eq!(result.envelope, case["expected_envelope"].as_str().unwrap());
        let mut shadow = policy.clone();
        shadow.mode = RoutingMode::Shadow;
        let chosen = executors::routing::choose_assessed(
            &shadow,
            result.floor,
            &result.envelope,
            &models,
            &availability,
            availability.observed_at,
        )
        .unwrap();
        assert_eq!(chosen.0, case["expected_shadow_model"].as_str().unwrap());
        println!(
            "captured execution {} -> {}; recommendation={:?}; same pid={}",
            case["execution"],
            result.envelope,
            chosen,
            std::process::id()
        );
    }
}

#[test]
#[ignore = "requires mounted SSD, strip and permitted bubblewrap user namespaces; zero inference"]
fn same_process_adopts_code_and_settings_then_rolls_back_safely() {
    let root = std::env::var_os("VK_ROUTING_TEST_ROOT").expect("Private test root required");
    let root = Path::new(&root).join(format!("reload-{}", std::process::id()));
    fs::create_dir(&root).unwrap();
    let home = root.join("private-codex-home");
    fs::create_dir(&home).unwrap();
    // One test in this standalone binary; initialize private process settings once
    // before helper threads. Native inference remains disabled throughout.
    unsafe {
        std::env::set_var("CODEX_HOME", &home);
        std::env::set_var("XDG_DATA_HOME", root.join("private-xdg"));
        std::env::set_var("VK_CODEX_ROUTING_MODULE", root.join("current"));
        std::env::set_var(
            "VK_CODEX_ROUTING_AVAILABILITY",
            root.join("fixture-availability.json"),
        );
    }
    // Synthetic qualification fixture, NOT executable-model/account evidence.
    let policies: Vec<executors::routing::ModelPolicy> =
        serde_json::from_str(include_str!("../src/routing_models.json")).unwrap();
    let now = chrono::Utc::now().timestamp();
    let availability = executors::routing::Availability {
        version: 1,
        observed_at: now,
        runtime: Some("fixture".into()),
        codex_home: home.canonicalize().unwrap().to_string_lossy().into_owned(),
        launcher: executors::executors::codex::Codex::base_command(),
        account_fingerprint: "fixture".into(),
        models: policies
            .iter()
            .map(|m| executors::routing::ModelAvailability {
                id: m.id.clone(),
                discovered: true,
                supported_efforts: m.efforts.clone(),
                verified_efforts: m.efforts.clone(),
                verified_at: Some(now),
            })
            .collect(),
    };
    fs::write(
        root.join("fixture-availability.json"),
        serde_json::to_vec(&availability).unwrap(),
    )
    .unwrap();
    let worker = Path::new(env!("CARGO_BIN_EXE_vk-routing-module"));
    release(&root, "a", worker, None);
    // Reproduce the old biases in replaceable code, then load the corrected
    // real Rust worker into the SAME running backend. No backend rebuild/restart.
    release(
        &root,
        "legacy_bias",
        worker,
        Some(
            "#!/usr/bin/python3\nimport json,sys\nr=json.load(sys.stdin)\na=r['seed']\nif 'production' in r['prompt'] or 'deploy' in r['prompt']:\n a['envelope']='protected';a['floor']='frontier';a['triage']['risk'].append('explicit_high_impact_intent')\nif r['stage']=='after' and r['previous_envelope']=='protected':\n a['envelope']='protected';a['floor']='frontier';a['evidence']='retained_session_qualification'\nprint(json.dumps({'protocol':2,'assessment':a,'needs_semantic':False}))\n",
        ),
    );
    // Different worker CODE, not only a changed prompt or preference rank.
    release(
        &root,
        "b",
        worker,
        Some(
            "#!/usr/bin/python3\nimport json,sys\nr=json.load(sys.stdin)\na=r['seed']\nif a['envelope']=='mechanical':\n a['envelope']='bounded'\n a['evidence']='updated_classification'\nprint(json.dumps({'protocol':2,'assessment':a,'needs_semantic':False}))\n",
        ),
    );
    release(
        &root,
        "timeout",
        worker,
        Some("#!/usr/bin/python3\nimport time\ntime.sleep(10)\n"),
    );
    release(
        &root,
        "oversize",
        worker,
        Some("#!/usr/bin/python3\nprint('x'*70000)\n"),
    );
    release(&root, "corrupt", worker, None);
    release(&root, "legacy_protocol", worker, None);
    let legacy_manifest = root.join("legacy_protocol/manifest.json");
    let mut manifest: serde_json::Value =
        serde_json::from_slice(&fs::read(&legacy_manifest).unwrap()).unwrap();
    manifest["protocol"] = 1.into();
    fs::write(legacy_manifest, serde_json::to_vec(&manifest).unwrap()).unwrap();
    release(
        &root,
        "unsafe_policy",
        worker,
        Some(
            "#!/usr/bin/python3\nimport json,sys\nr=json.load(sys.stdin)\na=r['seed']\na['envelope']='mechanical';a['floor']='routine';a['triage']['risk']=[]\nprint(json.dumps({'protocol':2,'assessment':a,'needs_semantic':False}))\n",
        ),
    );
    fs::write(root.join("corrupt/models.json"), "[]").unwrap();
    publish(&root, "a");
    let policy = RoutingPolicy {
        mode: RoutingMode::Auto,
        floor: CapabilityFloor::Assessed,
        denied_models: vec![],
        allow_escalation: false,
    };
    let sentinel = root.join("dirty-working-state");
    fs::write(&sentinel, "preserve me").unwrap();
    let pid = std::process::id();
    let caution = "Fix spelling typos in README.md. No production deployment.";
    let prompt =
        "Record the settled choice in the existing notes; do not redesign the architecture";
    let class = serde_json::json!({"envelope":"bounded","scope_relation":"bounded_step","scope":"localized",
        "novelty":"established","ambiguity":"low","horizon":"short","validation":"text_comparison",
        "risks":[],"uncertainty":"low","inspection_needed":false,"reason":"Record a settled choice in existing notes."});
    publish(&root, "legacy_bias");
    let old_scope = Scope::for_path(&root.join("current"));
    assert_eq!(assess(&policy, caution).floor, CapabilityFloor::Frontier);
    assert_eq!(
        captured_step(&root, &policy, prompt, class.clone())
            .assessment
            .floor,
        CapabilityFloor::Frontier
    );
    let old_action = routed(&policy, caution);
    assert_eq!(
        old_action
            .routing_decision
            .unwrap()
            .selected_model
            .as_deref(),
        Some("gpt-6-astra")
    );
    publish(&root, "a");
    assert_eq!(assess(&policy, caution).floor, CapabilityFloor::Frontier); // admitted snapshot pinned
    drop(old_scope);
    {
        let _scope = Scope::for_path(&root.join("current"));
        assert_eq!(assess(&policy, caution).floor, CapabilityFloor::Routine);
        let corrected = captured_step(&root, &policy, prompt, class);
        assert_eq!(corrected.assessment.floor, CapabilityFloor::Routine);
        assert!(
            corrected
                .assessment
                .triage
                .evidence
                .contains(&"surrounding_assignment:protected".into())
        );
        let corrected_action = routed(&policy, caution);
        assert_eq!(
            corrected_action
                .routing_decision
                .unwrap()
                .selected_model
                .as_deref(),
            Some("gpt-5.6-luna")
        );
        let continued = routing_module::assess(
            "continue",
            None,
            Some("Notes updated."),
            Some("protected"),
            Some(&root),
            false,
            &policy,
            false,
            serde_json::Value::Null,
        )
        .0;
        assert_eq!(continued.floor, CapabilityFloor::Frontier);
        replay_completed_assessments(&root, &policy);
    }
    assert_eq!(std::process::id(), pid);
    println!(
        "same pid={pid}: negative deployment interpretation and protected-history policy changed through worker publication; cheap model selection reached admission; generic resume remains protected"
    );
    let scope_a = Scope::for_path(&root.join("current"));
    let start = Instant::now();
    let first = assess(&policy, "Fix spelling typos in README.md");
    println!(
        "initial module evidence: {}",
        serde_json::to_string(&first.triage.evidence).unwrap()
    );
    assert_eq!(first.envelope, "mechanical");
    assert!(
        first
            .triage
            .evidence
            .iter()
            .any(|e| e.starts_with("routing_module:a:"))
    );
    let actual_a = routed(&policy, "Fix spelling typos in README.md");
    assert_eq!(
        executors::routing::config(&actual_a)
            .unwrap()
            .model_id
            .as_deref(),
        Some("gpt-5.6-luna")
    );
    assert_eq!(
        executors::routing::config(&actual_a)
            .unwrap()
            .reasoning_id
            .as_deref(),
        Some("low")
    );
    publish(&root, "b");
    // An already-admitted request keeps its original release.
    assert_eq!(
        assess(&policy, "Fix spelling typos in README.md").envelope,
        "mechanical"
    );
    assert!(routing_module::classifier().unwrap().2.ends_with('a'));
    drop(scope_a);
    {
        let _scope = Scope::for_path(&root.join("current"));
        assert_eq!(
            assess(&policy, "Fix spelling typos in README.md").envelope,
            "bounded"
        );
        let actual_b = routed(&policy, "Fix spelling typos in README.md");
        assert_eq!(
            executors::routing::config(&actual_b)
                .unwrap()
                .model_id
                .as_deref(),
            Some("gpt-6-luna")
        );
        assert_eq!(
            executors::routing::config(&actual_b)
                .unwrap()
                .reasoning_id
                .as_deref(),
            Some("medium")
        );
        let mut shadow = policy.clone();
        shadow.mode = RoutingMode::Shadow;
        let action = routed(&shadow, "Fix spelling typos in README.md");
        assert_eq!(
            executors::routing::config(&action)
                .unwrap()
                .model_id
                .as_deref(),
            Some("gpt-6-astra")
        );
        assert_eq!(
            action.routing_decision.unwrap().selected_model.as_deref(),
            Some("gpt-6-sol")
        );
        let normal = routed(&policy, "Fix this issue");
        assert_eq!(
            executors::routing::config(&normal)
                .unwrap()
                .model_id
                .as_deref(),
            Some("gpt-6-sol")
        );
        let mut excluded = policy.clone();
        excluded.denied_models.push("gpt-6-sol".into());
        let next = routed(&excluded, "Fix this issue");
        assert_ne!(
            executors::routing::config(&next)
                .unwrap()
                .model_id
                .as_deref(),
            Some("gpt-6-sol")
        );
        assert_eq!(routing_module::classifier().unwrap().0, "gpt-6-luna");
        assert_eq!(routing_module::classifier().unwrap().1, "medium");
        assert!(routing_module::classifier().unwrap().2.ends_with('b'));
        assert_eq!(
            assess(&policy, "Change authentication permissions").floor,
            CapabilityFloor::Frontier
        );
    }
    for bad in [
        "timeout",
        "oversize",
        "corrupt",
        "legacy_protocol",
        "unsafe_policy",
        "missing",
    ] {
        publish(&root, bad);
        let update_start = Instant::now();
        let _scope = Scope::for_path(&root.join("current"));
        let a = assess(&policy, "Fix spelling typos in README.md");
        assert_eq!(a.envelope, "bounded");
        assert!(
            a.triage
                .evidence
                .iter()
                .any(|e| e == "routing_module_warning:update_rejected")
        );
        if bad == "timeout" {
            // The ten-second helper must be terminated, without waiting for it.
            assert!(update_start.elapsed().as_secs() < 5);
        }
    }
    publish(&root, "a");
    {
        let _scope = Scope::for_path(&root.join("current"));
        assert_eq!(
            assess(&policy, "Fix spelling typos in README.md").envelope,
            "mechanical"
        );
    }
    let parent = routed(&policy, "Fix spelling typos in README.md")
        .routing_decision
        .unwrap();
    let assignment = executors::routing_delegation::Assignment {
        task: "docs".into(),
        message: "Fix spelling typos in README.md".into(),
        context: "Preserve meaning.".into(),
        paths: vec!["README.md".into()],
        independent: true,
        size: "batch".into(),
        read_only: false,
    };
    let mut strong_parent = parent.clone();
    strong_parent.floor = CapabilityFloor::Workhorse;
    strong_parent.assessed_envelope = Some("normal".into());
    let child = executors::routing_delegation::choose(
        &assignment,
        &root,
        &policy,
        &strong_parent,
        None,
        false,
        false,
    )
    .unwrap();
    assert_eq!(
        (child.model.as_str(), child.effort.as_str()),
        ("gpt-5.6-luna", "low")
    );
    assert!(child.source.contains("routing_module:a:"));
    let mut protected = strong_parent.clone();
    protected.floor = CapabilityFloor::Frontier;
    protected.assessed_envelope = Some("protected".into());
    let protected_child = executors::routing_delegation::choose(
        &assignment,
        &root,
        &policy,
        &protected,
        None,
        false,
        false,
    )
    .unwrap();
    assert_eq!(protected_child.model, "gpt-6-astra");
    let mut escalation = policy.clone();
    escalation.allow_escalation = true;
    let recovery = executors::routing_delegation::choose(
        &assignment,
        &root,
        &escalation,
        &strong_parent,
        Some(&child),
        true,
        false,
    )
    .unwrap();
    assert_eq!(
        (recovery.model.as_str(), recovery.effort.as_str()),
        ("gpt-6.1-sol", "medium")
    );
    assert!(recovery.escalated);
    let mut manual = policy.clone();
    manual.mode = RoutingMode::Manual;
    let manual = routed(&manual, "Fix spelling typos in README.md");
    assert_eq!(
        executors::routing::config(&manual)
            .unwrap()
            .model_id
            .as_deref(),
        Some("gpt-6-astra")
    );
    assert_eq!(
        executors::routing::config(&manual)
            .unwrap()
            .reasoning_id
            .as_deref(),
        Some("high")
    );
    assert!(manual.routing_decision.is_none());
    // No compatible cached release: fall back visibly to the built-in router.
    let empty = root.join("no-release");
    {
        let _scope = Scope::for_path(&empty);
        let fallback = assess(&policy, "Fix spelling typos in README.md");
        assert_eq!(fallback.envelope, "mechanical");
        assert!(
            fallback
                .triage
                .evidence
                .contains(&"routing_module_warning:update_rejected".into())
        );
    }
    assert_eq!(pid, std::process::id());
    assert_eq!(fs::read_to_string(&sentinel).unwrap(), "preserve me");
    println!(
        "same pid={pid}; code/prompt reload, pinned in-flight snapshot, last-good timeout/oversize/missing fallback, rollback, hard risk and dirty sentinel passed; elapsed_ms={}",
        start.elapsed().as_millis()
    );
}

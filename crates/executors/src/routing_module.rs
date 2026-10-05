//! Replaceable pure triage, with native execution and safety retained by VK.
use std::{
    cell::RefCell,
    collections::HashMap,
    io::{Read, Write},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::{Arc, Mutex, OnceLock, mpsc},
    time::{Duration, Instant},
};

use command_group::CommandGroup;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::{
    routing::{CapabilityFloor, ModelPolicy, RoutingPolicy},
    routing_assessment::Assessment,
    routing_semantic::{SemanticClass, SemanticTrace},
    routing_triage::TaskTriage,
};

const LIMIT: u64 = 65536;
const DEADLINE: Duration = Duration::from_millis(750);

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct WireAssessment {
    pub envelope: String,
    pub floor: CapabilityFloor,
    pub evidence: String,
    pub validation_failure: bool,
    pub triage: TaskTriage,
}
impl From<&Assessment> for WireAssessment {
    fn from(a: &Assessment) -> Self {
        Self {
            envelope: a.envelope.into(),
            floor: a.floor,
            evidence: a.evidence.clone(),
            validation_failure: a.validation_failure,
            triage: a.triage.clone(),
        }
    }
}
impl WireAssessment {
    pub fn into_assessment(self) -> Result<Assessment, String> {
        let envelope = match self.envelope.as_str() {
            "mechanical" => "mechanical",
            "bounded" => "bounded",
            "validated_fix" => "validated_fix",
            "normal" => "normal",
            "complex" => "complex",
            "protected" => "protected",
            _ => return Err("Unsupported module envelope".into()),
        };
        let minimum = match envelope {
            "mechanical" | "bounded" => CapabilityFloor::Routine,
            "protected" => CapabilityFloor::Frontier,
            _ => CapabilityFloor::Workhorse,
        };
        if self.floor < minimum || self.evidence.len() > 160 || self.triage.evidence.len() > 40 {
            return Err("Invalid module assessment".into());
        }
        Ok(Assessment {
            envelope,
            floor: self.floor,
            evidence: self.evidence,
            validation_failure: self.validation_failure,
            triage: self.triage,
        })
    }
}

#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub protocol: u32,
    pub stage: String,
    pub prompt: String,
    pub previous_envelope: Option<String>,
    pub completed_reply: Option<String>,
    pub failed: bool,
    pub policy: RoutingPolicy,
    pub seed: WireAssessment,
    pub semantic: Option<serde_json::Value>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Reply {
    pub protocol: u32,
    pub assessment: WireAssessment,
    pub needs_semantic: bool,
}

/// Pure worker implementation: no native runtime, repository reads or tools.
pub fn evaluate(request: Request) -> Result<Reply, String> {
    if request.protocol != 1 || !["before", "after"].contains(&request.stage.as_str()) {
        return Err("Unsupported routing module protocol".into());
    }
    let mut a = request.seed.into_assessment()?;
    if request.stage == "before" {
        crate::routing_context::apply_reference_context(
            &mut a,
            &request.prompt,
            request.completed_reply.as_deref(),
        );
    } else {
        if let Some(value) = request.semantic {
            let class: SemanticClass =
                serde_json::from_value(value).map_err(|_| "Invalid semantic input")?;
            crate::routing_semantic::apply(&mut a, &class);
        }
        a = crate::routing_assessment::retain_previous(
            a,
            &request.prompt,
            request.previous_envelope.as_deref(),
        );
    }
    let needs_semantic = request.stage == "before"
        && crate::routing_semantic::eligible(
            &a,
            request.failed,
            &request.policy,
            &request.prompt,
            request.previous_envelope.as_deref(),
        );
    Ok(Reply {
        protocol: 1,
        assessment: (&a).into(),
        needs_semantic,
    })
}

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
pub struct Manifest {
    pub protocol: u32,
    pub version: String,
    pub worker_sha256: String,
    pub models_sha256: String,
    pub instructions_sha256: String,
    pub classifier_model: String,
    pub classifier_effort: String,
}
struct Release {
    root: PathBuf,
    manifest_hash: String,
    manifest: Manifest,
    models: Vec<ModelPolicy>,
    instructions: String,
    stamps: Vec<(u64, Option<std::time::SystemTime>)>,
}
#[derive(Default, Clone)]
struct Active {
    release: Option<Arc<Release>>,
    warning: Option<&'static str>,
}
thread_local! { static ACTIVE: RefCell<Active> = RefCell::new(Active::default()); }
type Cache = HashMap<PathBuf, Arc<Release>>;
static GOOD: OnceLock<Mutex<Cache>> = OnceLock::new();

pub struct Scope(Active);
impl Scope {
    pub fn for_path(path: &Path) -> Self {
        Self(ACTIVE.with(|a| a.replace(load(path))))
    }
    pub fn enter() -> Self {
        let active = match std::env::var_os("VK_CODEX_ROUTING_MODULE") {
            None => Active::default(),
            Some(path) => load(Path::new(&path)),
        };
        Self(ACTIVE.with(|a| a.replace(active)))
    }
}
impl Drop for Scope {
    fn drop(&mut self) {
        ACTIVE.with(|a| a.replace(self.0.clone()));
    }
}

fn read(path: &Path, limit: u64) -> Result<Vec<u8>, String> {
    let meta = std::fs::symlink_metadata(path).map_err(|_| "Missing module artifact")?;
    if !meta.is_file() || meta.len() > limit {
        return Err("Invalid module artifact".into());
    }
    let mut data = Vec::new();
    std::fs::File::open(path)
        .map_err(|_| "Unreadable module artifact")?
        .take(limit + 1)
        .read_to_end(&mut data)
        .map_err(|_| "Unreadable module artifact")?;
    if data.len() as u64 > limit {
        return Err("Oversized module artifact".into());
    }
    Ok(data)
}
fn digest(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn worker_digest(path: &Path) -> Result<String, String> {
    let meta = std::fs::symlink_metadata(path).map_err(|_| "Missing worker")?;
    if !meta.is_file() || meta.len() > 256 * 1024 * 1024 {
        return Err("Invalid worker".into());
    }
    let mut file = std::fs::File::open(path).map_err(|_| "Unreadable worker")?;
    let mut hasher = Sha256::new();
    let mut buffer = [0u8; 65536];
    loop {
        let n = file.read(&mut buffer).map_err(|_| "Unreadable worker")?;
        if n == 0 {
            break;
        }
        hasher.update(&buffer[..n]);
    }
    Ok(format!("{:x}", hasher.finalize()))
}

fn stamps(root: &Path) -> Result<Vec<(u64, Option<std::time::SystemTime>)>, String> {
    ["worker", "models.json", "instructions.txt"]
        .iter()
        .map(|name| {
            let meta = std::fs::symlink_metadata(root.join(name))
                .map_err(|_| "Missing immutable artifact")?;
            if !meta.is_file() {
                return Err("Invalid immutable artifact".into());
            }
            Ok((meta.len(), meta.modified().ok()))
        })
        .collect()
}

fn load_release(path: &Path, previous: Option<&Arc<Release>>) -> Result<Arc<Release>, String> {
    if !path.is_absolute() {
        return Err("Module path must be absolute".into());
    }
    let root = path.canonicalize().map_err(|_| "Missing module release")?;
    let data = read(&root.join("manifest.json"), LIMIT)?;
    let hash = digest(&data);
    if let Some(previous) = previous.filter(|p| p.root == root && p.manifest_hash == hash) {
        if stamps(&root)? != previous.stamps {
            return Err("Immutable module release was modified".into());
        }
        return Ok(previous.clone());
    }
    let manifest: Manifest =
        serde_json::from_slice(&data).map_err(|_| "Invalid module manifest")?;
    if manifest.protocol != 1
        || manifest.version.is_empty()
        || manifest.version.len() > 80
        || !manifest
            .version
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || "._-".contains(c))
    {
        return Err("Unsupported module manifest".into());
    }
    let models = read(&root.join("models.json"), LIMIT)?;
    let instructions = read(&root.join("instructions.txt"), 16384)?;
    // Only on release adoption, never every routing call.
    if worker_digest(&root.join("worker"))? != manifest.worker_sha256
        || digest(&models) != manifest.models_sha256
        || digest(&instructions) != manifest.instructions_sha256
    {
        return Err("Module artifact hash mismatch".into());
    }
    let models = crate::routing::parse_model_policies(&models)?;
    if !models.iter().any(|m| {
        m.id == manifest.classifier_model && m.efforts.contains(&manifest.classifier_effort)
    }) {
        return Err("Classifier is absent from module policy".into());
    }
    let instructions =
        String::from_utf8(instructions).map_err(|_| "Invalid module instructions")?;
    if instructions.trim().is_empty() {
        return Err("Empty module instructions".into());
    }
    let stamps = stamps(&root)?;
    let release = Arc::new(Release {
        root,
        manifest_hash: hash,
        manifest,
        models,
        instructions,
        stamps,
    });
    let request = probe_request();
    checked(invoke(&release, &request)?, &request)?;
    Ok(release)
}

fn probe_request() -> Request {
    Request {
        protocol: 1,
        stage: "before".into(),
        prompt: "Fix spelling typos in README.md".into(),
        previous_envelope: None,
        completed_reply: None,
        failed: false,
        policy: RoutingPolicy {
            mode: crate::routing::RoutingMode::Shadow,
            floor: CapabilityFloor::Assessed,
            denied_models: vec![],
            allow_escalation: false,
        },
        seed: (&crate::routing_assessment::assess("Fix spelling typos in README.md")).into(),
        semantic: None,
    }
}

pub fn verify_release(path: &Path) -> Result<serde_json::Value, String> {
    let release = load_release(path, None)?;
    Ok(
        serde_json::json!({"protocol":1,"version":release.manifest.version,"manifestHash":release.manifest_hash,
        "root":release.root,"workerSha256":release.manifest.worker_sha256,"models":release.models.iter().map(|m| &m.id).collect::<Vec<_>>(),
        "classifierModel":release.manifest.classifier_model,"classifierEffort":release.manifest.classifier_effort,"sandboxVerified":true}),
    )
}
fn load(path: &Path) -> Active {
    let mut good = GOOD
        .get_or_init(|| Mutex::new(HashMap::new()))
        .lock()
        .unwrap_or_else(|e| e.into_inner());
    let previous = good.get(path).cloned();
    match load_release(path, previous.as_ref()) {
        Ok(release) => {
            good.insert(path.into(), release.clone());
            Active {
                release: Some(release),
                warning: None,
            }
        }
        Err(error) => {
            tracing::warn!(%error, "AutoSwitch module update rejected; retaining safe routing");
            Active {
                release: previous.filter(|p| stamps(&p.root).is_ok_and(|s| s == p.stamps)),
                warning: Some("update_rejected"),
            }
        }
    }
}
pub fn models() -> Option<Vec<ModelPolicy>> {
    ACTIVE.with(|a| a.borrow().release.as_ref().map(|r| r.models.clone()))
}
pub fn classifier() -> Option<(String, String, String)> {
    ACTIVE.with(|a| {
        a.borrow().release.as_ref().map(|r| {
            (
                r.manifest.classifier_model.clone(),
                r.manifest.classifier_effort.clone(),
                r.instructions.clone(),
            )
        })
    })
}
fn mark(a: &mut Assessment) {
    ACTIVE.with(|active| {
        let active = active.borrow();
        if let Some(r) = &active.release {
            a.triage.evidence.push(format!(
                "routing_module:{}:{}",
                r.manifest.version, r.manifest_hash
            ));
        }
        if let Some(warning) = active.warning {
            a.triage
                .evidence
                .push(format!("routing_module_warning:{warning}"));
        }
    });
}

pub fn source(a: &Assessment) -> String {
    let module: Vec<_> = a
        .triage
        .evidence
        .iter()
        .filter(|e| e.starts_with("routing_module"))
        .cloned()
        .collect();
    if module.is_empty() {
        a.evidence.clone()
    } else {
        format!("{};{}", a.evidence, module.join(";"))
    }
}

pub fn warning() -> Option<&'static str> {
    ACTIVE.with(|a| a.borrow().warning)
}

fn invoke(release: &Release, request: &Request) -> Result<Reply, String> {
    let input = serde_json::to_vec(request).map_err(|_| "Invalid module input")?;
    if input.len() as u64 > LIMIT {
        return Err("Module context exceeds limit".into());
    }
    let sandbox = std::env::split_paths(&std::env::var_os("PATH").unwrap_or_default())
        .map(|p| p.join("bwrap"))
        .find(|p| p.is_file())
        .ok_or("Module sandbox unavailable")?;
    let mut command = Command::new("/usr/bin/prlimit");
    command
        .env_clear()
        .args(["--as=536870912", "--cpu=1", "--"])
        .arg(sandbox)
        .args([
            "--die-with-parent",
            "--unshare-all",
            "--new-session",
            "--ro-bind",
            "/usr",
            "/usr",
            "--ro-bind",
            "/lib",
            "/lib",
            "--ro-bind",
            "/lib64",
            "/lib64",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--ro-bind",
        ])
        .arg(&release.root)
        .arg("/module")
        .args([
            "--remount-ro",
            "/tmp",
            "--chdir",
            "/module",
            "--clearenv",
            "/module/worker",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    let mut child = command
        .group_spawn()
        .map_err(|_| "Module sandbox unavailable")?;
    let mut stdin = child
        .inner()
        .stdin
        .take()
        .ok_or("Missing module input pipe")?;
    let stdout = child
        .inner()
        .stdout
        .take()
        .ok_or("Missing module output pipe")?;
    let writer = std::thread::spawn(move || stdin.write_all(&input));
    let (tx, rx) = mpsc::channel();
    let reader = std::thread::spawn(move || {
        let mut bytes = Vec::new();
        let result = stdout.take(LIMIT + 1).read_to_end(&mut bytes);
        let _ = tx.send((result, bytes));
    });
    let received = rx.recv_timeout(DEADLINE);
    // Kill the entire helper group even after output, including stray descendants.
    let status = child.inner().try_wait().ok().flatten();
    let _ = child.kill();
    let _ = child.wait();
    let written = writer.join().ok().is_some_and(|r| r.is_ok());
    let _ = reader.join();
    let (read, bytes) = received.map_err(|_| "Module deadline exceeded")?;
    if read.is_err()
        || !written
        || bytes.len() as u64 > LIMIT
        || status.is_some_and(|s| !s.success())
    {
        return Err("Module process failed".into());
    }
    let reply: Reply = serde_json::from_slice(&bytes).map_err(|_| "Invalid module output")?;
    if reply.protocol != 1 {
        return Err("Unsupported module reply".into());
    }
    Ok(reply)
}

fn checked(mut reply: Reply, request: &Request) -> Result<Reply, String> {
    let a = reply.assessment.clone().into_assessment()?;
    let seed = &request.seed;
    if (seed.validation_failure && !a.validation_failure)
        || seed.triage.risk.iter().any(|r| !a.triage.risk.contains(r))
        || ((seed.floor == CapabilityFloor::Frontier || !a.triage.risk.is_empty())
            && (a.floor != CapabilityFloor::Frontier || a.envelope != "protected"))
        || ((request.failed || seed.validation_failure) && a.floor < seed.floor)
    {
        return Err("Module attempted to weaken hard evidence".into());
    }
    if let Some(value) = &request.semantic {
        let class: SemanticClass =
            serde_json::from_value(value.clone()).map_err(|_| "Invalid semantic evidence")?;
        if !crate::routing_semantic::validate(&class) {
            return Err("Invalid semantic evidence".into());
        }
        if ((!class.risks.is_empty() || class.envelope == "protected")
            && (a.floor != CapabilityFloor::Frontier || a.envelope != "protected"))
            || class.risks.iter().any(|r| !a.triage.risk.contains(r))
            || ((class.envelope == "complex"
                || class.scope == "cross_cutting"
                || class.novelty == "novel"
                || class.horizon == "extended")
                && a.floor < CapabilityFloor::Workhorse)
        {
            return Err("Module attempted to erase semantic risk or complexity evidence".into());
        }
    }
    if request.stage == "after"
        && let Some(prior) = &request.previous_envelope
    {
        let prior_floor = match prior.as_str() {
            "mechanical" | "bounded" => CapabilityFloor::Routine,
            "validated_fix" | "normal" | "complex" => CapabilityFloor::Workhorse,
            _ => CapabilityFloor::Frontier,
        };
        if a.floor < prior_floor {
            let known = [
                "mechanical",
                "bounded",
                "validated_fix",
                "normal",
                "complex",
                "protected",
            ]
            .contains(&prior.as_str());
            let safe_step = request.completed_reply.is_some()
                && crate::routing_context::reassess_step(&a, &request.prompt, prior);
            if !known
                || !(safe_step
                    || (prior != "protected"
                        && crate::routing_assessment::independent_request(&a, &request.prompt)))
            {
                return Err("Module attempted to discard protected session context".into());
            }
            let surrounding = format!("surrounding_assignment:{prior}");
            if !reply.assessment.triage.evidence.contains(&surrounding) {
                reply.assessment.triage.evidence.push(surrounding);
            }
        }
    }
    Ok(reply)
}
fn run(request: &Request) -> Option<Reply> {
    let release = ACTIVE.with(|a| {
        let a = a.borrow();
        if a.warning == Some("worker_failed") {
            None
        } else {
            a.release.clone()
        }
    })?;
    let started = Instant::now();
    let result = invoke(&release, request).and_then(|r| checked(r, request));
    tracing::debug!(version=%release.manifest.version, elapsed_ms=started.elapsed().as_millis(), stage=%request.stage, "AutoSwitch module evaluated");
    match result {
        Ok(mut reply) => {
            reply.assessment.triage.evidence.push(format!(
                "routing_module_{}_ms:{}",
                request.stage,
                started.elapsed().as_millis()
            ));
            Some(reply)
        }
        Err(error) => {
            tracing::warn!(%error, "AutoSwitch module failed; built-in assessment retained");
            ACTIVE.with(|a| a.borrow_mut().warning = Some("worker_failed"));
            None
        }
    }
}

/// Uses one pinned release for deterministic, semantic, history and policy stages.
#[allow(clippy::too_many_arguments)]
pub fn assess(
    prompt: &str,
    previous_prompt: Option<&str>,
    completed_reply: Option<&str>,
    previous_envelope: Option<&str>,
    root: Option<&Path>,
    failed: bool,
    policy: &RoutingPolicy,
    semantic_enabled: bool,
    correlation: serde_json::Value,
) -> (Assessment, Option<SemanticTrace>) {
    let mut a = crate::routing_assessment::assess_with_context(prompt, root);
    let reply = completed_reply.filter(|r| !failed && !r.trim().is_empty());
    let mut request = Request {
        protocol: 1,
        stage: "before".into(),
        prompt: prompt.chars().take(6144).collect(),
        previous_envelope: previous_envelope.map(str::to_owned),
        completed_reply: reply.map(|s| s.chars().take(3000).collect()),
        failed,
        policy: policy.clone(),
        seed: (&a).into(),
        semantic: None,
    };
    let pre = run(&request);
    let want_semantic = pre.as_ref().map(|r| r.needs_semantic);
    if let Some(pre) = pre {
        a = pre
            .assessment
            .into_assessment()
            .expect("checked module output");
    } else {
        crate::routing_context::apply_reference_context(&mut a, prompt, reply);
    }
    let hard_allows = !failed
        && !a.validation_failure
        && a.triage.risk.is_empty()
        && a.floor != CapabilityFloor::Frontier
        && policy.floor != CapabilityFloor::Frontier
        && !(previous_envelope.is_some() && crate::routing_assessment::is_continuation(prompt));
    let semantic = if semantic_enabled
        && hard_allows
        && want_semantic.unwrap_or_else(|| {
            crate::routing_semantic::eligible(&a, failed, policy, prompt, previous_envelope)
        }) {
        Some(crate::routing_semantic::classify_with_context_scoped(
            prompt,
            previous_prompt,
            reply,
            &a,
            policy,
            correlation,
        ))
    } else {
        None
    };
    request.stage = "after".into();
    request.seed = (&a).into();
    if let Some(class) = semantic.as_ref().and_then(|t| t.classification.as_ref()) {
        let mut value = serde_json::to_value(class).expect("serializable classification");
        value["scope_relation"] = serde_json::json!(class.scope_relation);
        request.semantic = Some(value);
    }
    if let Some(post) = run(&request) {
        a = post
            .assessment
            .into_assessment()
            .expect("checked module output");
    } else {
        if let Some(class) = semantic.as_ref().and_then(|t| t.classification.as_ref()) {
            crate::routing_semantic::apply(&mut a, class);
        }
        a = crate::routing_assessment::retain_previous(a, prompt, previous_envelope);
    }
    mark(&mut a);
    (a, semantic)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adapter_cannot_erase_risk_failures_or_protected_history() {
        let mut request = probe_request();
        request.prompt = "Change authentication permissions".into();
        request.seed = (&crate::routing_assessment::assess(&request.prompt)).into();
        let cheap = evaluate(probe_request()).unwrap();
        assert!(checked(cheap, &request).is_err());
        request.seed.validation_failure = true;
        assert!(checked(evaluate(probe_request()).unwrap(), &request).is_err());
        request = probe_request();
        request.stage = "after".into();
        request.semantic = Some(
            serde_json::json!({"envelope":"protected","scope_relation":"independent","scope":"localized",
            "novelty":"established","ambiguity":"low","horizon":"short","validation":"deterministic_test",
            "risks":["security"],"uncertainty":"low","inspection_needed":false,"reason":"Protected change"}),
        );
        assert!(checked(evaluate(probe_request()).unwrap(), &request).is_err());
        request = probe_request();
        request.stage = "after".into();
        request.previous_envelope = Some("protected".into());
        request.prompt = "Continue".into();
        assert!(checked(evaluate(probe_request()).unwrap(), &request).is_err());
        request.previous_envelope = Some("future_unknown_envelope".into());
        assert!(checked(evaluate(probe_request()).unwrap(), &request).is_err());
    }

    #[test]
    fn compatible_worker_preserves_reference_and_diagnostic_guards() {
        let mut request = probe_request();
        request.prompt = "What are the actual component dimensions?".into();
        request.seed = (&crate::routing_assessment::assess(&request.prompt)).into();
        request.completed_reply = Some("Chosen component: 40 mm".into());
        request.previous_envelope = Some("protected".into());
        let pre = checked(
            evaluate(serde_json::from_value(serde_json::to_value(&request).unwrap()).unwrap())
                .unwrap(),
            &request,
        )
        .unwrap();
        assert_eq!(pre.assessment.envelope, "bounded");
        assert!(!pre.needs_semantic);
        request.seed = pre.assessment;
        request.stage = "after".into();
        let post = checked(
            evaluate(serde_json::from_value(serde_json::to_value(&request).unwrap()).unwrap())
                .unwrap(),
            &request,
        )
        .unwrap();
        assert_eq!(post.assessment.floor, CapabilityFloor::Routine);
        assert!(
            post.assessment
                .triage
                .evidence
                .contains(&"surrounding_assignment:protected".into())
        );
        let a = post.assessment.into_assessment().unwrap();
        assert_eq!(
            crate::routing_assessment::boundary_floor(&a, CapabilityFloor::Frontier, None),
            CapabilityFloor::Frontier
        );
    }
}

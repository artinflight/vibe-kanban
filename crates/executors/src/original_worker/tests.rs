use std::sync::atomic::{AtomicBool, Ordering};

use serde_json::json;
use tokio::sync::Notify;

use super::*;
use crate::{
    actions::{Executable, coding_agent_follow_up::CodingAgentFollowUpRequest},
    approvals::NoopExecutorApprovalService,
    env::RepoContext,
    executors::{BaseCodingAgent, CodingAgent, StandardCodingAgentExecutor},
    profile::{ExecutorConfig, ExecutorConfigs},
};

#[derive(Debug)]
struct Pinned {
    raw: ExecutorConfig,
    pin: String,
    cloned: Notify,
    inspect: Notify,
    checked: AtomicBool,
}
#[async_trait]
impl LaunchGuard for Pinned {
    fn worker(&self) -> bool {
        true
    }
    async fn resolved(&self, agent: &CodingAgent, raw: &ExecutorConfig) -> io::Result<()> {
        self.cloned.notify_one();
        self.inspect.notified().await;
        verify_resolved(agent, raw, &self.raw, &self.pin)?;
        self.checked.store(true, Ordering::SeqCst);
        Ok(())
    }
    async fn activation(&self, _: &str, _: Option<&str>) -> io::Result<ActivationFence> {
        Err(io::Error::other("No native process in this fixture"))
    }
}

#[tokio::test]
async fn actual_follow_up_cache_aba_rejected_before_prompt_or_launcher() {
    let original = ExecutorConfigs::get_cached();
    struct Restore(ExecutorConfigs);
    impl Drop for Restore {
        fn drop(&mut self) {
            ExecutorConfigs::replace_cache_for_test(self.0.clone());
        }
    }
    let _restore = Restore(original.clone());
    let raw: ExecutorConfig = serde_json::from_value(json!({"executor":"CODEX","variant":"DEFAULT","model_id":"gpt-6.1-sol","reasoning_id":"high"})).unwrap();
    let mut a = original.get_coding_agent(&raw.profile_id()).unwrap();
    a.apply_overrides(&raw);
    let guard = Arc::new(Pinned {
        raw: raw.clone(),
        pin: profile_digest(&a).unwrap(),
        cloned: Notify::new(),
        inspect: Notify::new(),
        checked: AtomicBool::new(false),
    });
    let mut b = original.clone();
    let mut altered = a.clone();
    let CodingAgent::Codex(codex) = &mut altered else {
        panic!("Codex fixture")
    };
    codex.append_prompt =
        serde_json::from_value(json!("synthetic conflicting append prompt")).unwrap();
    codex.cmd.base_command_override = Some("synthetic-launcher-must-never-run".into());
    b.executors
        .get_mut(&BaseCodingAgent::Codex)
        .unwrap()
        .set_default(altered);
    ExecutorConfigs::replace_cache_for_test(b);
    let request = CodingAgentFollowUpRequest {
        prompt: "Synthetic fixed continuation".into(),
        executor_config: raw,
        session_id: "synthetic-thread".into(),
        reset_to_message_id: None,
        working_dir: None,
        capacity: None,
    };
    let mut env = ExecutionEnv::new(RepoContext::default(), false, String::new());
    env.original_worker = Some(guard.clone());
    let run = tokio::spawn(async move {
        request
            .spawn(
                std::path::Path::new("."),
                Arc::new(NoopExecutorApprovalService),
                &env,
            )
            .await
    });
    guard.cloned.notified().await;
    ExecutorConfigs::replace_cache_for_test(original);
    guard.inspect.notify_one();
    let error = match run.await.unwrap() {
        Err(error) => error,
        Ok(_) => panic!("B must be rejected after A was restored"),
    };
    assert!(
        error
            .to_string()
            .contains("Actual resolved launch instance")
    );
    assert!(!guard.checked.load(Ordering::SeqCst));
}

#[test]
fn load_preflight_rejects_active_and_unknown_goal_before_resume() {
    for v in [
        json!({}),
        json!({"goal":{"status":"active"}}),
        json!({"goal":{"status":"unknown"}}),
    ] {
        assert!(worker_goal_load_allowed(&v).is_err());
    }
    for v in [
        json!({"goal":null}),
        json!({"goal":{"status":"paused"}}),
        json!({"goal":{"status":"complete"}}),
    ] {
        worker_goal_load_allowed(&v).unwrap();
    }
}

#[derive(Debug)]
struct LoadFence(Arc<tokio::sync::Mutex<()>>);
#[async_trait]
impl LaunchGuard for LoadFence {
    fn worker(&self) -> bool { true }
    async fn resolved(&self, _: &CodingAgent, _: &ExecutorConfig) -> io::Result<()> { Ok(()) }
    async fn activation(&self, _: &str, _: Option<&str>) -> io::Result<ActivationFence> { Ok(self.0.clone().lock_owned().await) }
}

#[tokio::test]
async fn actual_thread_resume_checks_goal_before_loading_and_feedback_is_fenced() {
    use std::{process::Stdio, time::Duration};
    use tokio::io::{AsyncBufReadExt, BufReader};
    use tokio_util::sync::CancellationToken;
    use crate::executors::codex::{client::{AppServerClient, LogWriter}, jsonrpc::{ExitSignalSender, JsonRpcPeer}};
    for status in ["active", "unknown", "paused", "none"] {
        let mut child = tokio::process::Command::new("python3").args(["-u","-c",r#"
import json,sys
status=sys.argv[1]
for line in sys.stdin:
    q=json.loads(line); m=q['method']; print(m,file=sys.stderr,flush=True)
    if m=='thread/goal/get':
        r={} if status=='unknown' else {'goal':None if status=='none' else {'status':status}}
    else:
        t={'id':'synthetic-worker','preview':'synthetic','ephemeral':False,'modelProvider':'synthetic','createdAt':1,'updatedAt':1,'status':{'type':'idle'},'path':None,'cwd':'/synthetic','cliVersion':'0.159.2','source':'exec','turns':[]}
        r={'thread':t,'model':'gpt-6.1-sol','modelProvider':'synthetic','serviceTier':None,'cwd':'/synthetic','approvalPolicy':'on-request','approvalsReviewer':'user','sandbox':{'type':'readOnly'},'reasoningEffort':'high'}
    print(json.dumps({'id':q['id'],'result':r}),flush=True)
"#,status]).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).kill_on_drop(true).spawn().unwrap();
        let mut calls = BufReader::new(child.stderr.take().unwrap()).lines();
        let cancel = CancellationToken::new();
        let client = AppServerClient::new(LogWriter::new(tokio::io::sink()),None,false,false,RepoContext::default(),false,String::new(),cancel.clone());
        client.set_original_worker_guard(Arc::new(LoadFence(Arc::new(tokio::sync::Mutex::new(())))));
        let (tx,_rx) = tokio::sync::oneshot::channel();
        client.connect(JsonRpcPeer::spawn(child.stdin.take().unwrap(),child.stdout.take().unwrap(),client.clone(),ExitSignalSender::new(tx),cancel.clone()));
        let result = client.thread_resume(serde_json::from_value(json!({"threadId":"synthetic-worker"})).unwrap()).await;
        assert_eq!(calls.next_line().await.unwrap().as_deref(),Some("thread/goal/get"));
        if matches!(status,"active"|"unknown") {
            assert!(result.is_err());
            assert!(tokio::time::timeout(Duration::from_millis(100),calls.next_line()).await.is_err(),"active/unknown goal must never load");
        } else {
            result.unwrap();
            assert_eq!(calls.next_line().await.unwrap().as_deref(),Some("thread/resume"));
        }
        cancel.cancel(); child.kill().await.unwrap(); child.wait().await.unwrap();
    }
}

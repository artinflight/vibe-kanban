//! Explicit opt-in, existing-account acceptance. Never runs in ordinary CI.
use std::{
    io::{Read, Write},
    sync::atomic::{AtomicUsize, Ordering},
};

use async_trait::async_trait;
use sha2::{Digest, Sha256};
use tokio::io::AsyncReadExt;
use workspace_utils::approvals::{ApprovalStatus, QuestionStatus};

use super::*;
use crate::{approvals::ExecutorApprovalError, executors::acp::AcpAgentHarness};

struct DenyNative(AtomicUsize);
#[async_trait]
impl ExecutorApprovalService for DenyNative {
    fn supports_interactive_approvals(&self) -> bool {
        true
    }
    async fn create_tool_approval(&self, _: &str) -> Result<String, ExecutorApprovalError> {
        self.0.fetch_add(1, Ordering::SeqCst);
        Ok("bounded-native-denial".into())
    }
    async fn create_question_approval(
        &self,
        _: &str,
        _: usize,
    ) -> Result<String, ExecutorApprovalError> {
        Err(ExecutorApprovalError::ServiceUnavailable)
    }
    async fn wait_tool_approval(
        &self,
        _: &str,
        _: CancellationToken,
    ) -> Result<ApprovalStatus, ExecutorApprovalError> {
        Ok(ApprovalStatus::Denied { reason: None })
    }
    async fn wait_question_answer(
        &self,
        _: &str,
        _: CancellationToken,
    ) -> Result<QuestionStatus, ExecutorApprovalError> {
        Err(ExecutorApprovalError::ServiceUnavailable)
    }
}

async fn finish(mut child: SpawnedChild) -> (bool, String) {
    let stdout = child.child.inner().stdout.take().unwrap();
    let logs = tokio::spawn(async move {
        let mut text = String::new();
        stdout
            .take(2 * 1024 * 1024)
            .read_to_string(&mut text)
            .await
            .unwrap();
        text
    });
    let terminal =
        tokio::time::timeout(Duration::from_secs(120), child.exit_signal.take().unwrap()).await;
    let _ = child.child.kill().await;
    let _ = child.child.wait().await;
    let ok = matches!(terminal, Ok(Ok(ExecutorExitResult::Success)));
    (
        ok,
        tokio::time::timeout(Duration::from_secs(3), logs)
            .await
            .unwrap()
            .unwrap(),
    )
}

#[tokio::test]
#[ignore = "Requires explicit account authorization, mounted scratch and at most two real prompts"]
async fn antigravity_native_denial_and_bound_resume() {
    let root = PathBuf::from(
        std::env::var_os("VK_AG_NATIVE_TEST_ROOT").expect("explicit disposable SSD directory"),
    );
    assert!(root.is_absolute() && root.starts_with("/mnt/vk-storage") && root.is_dir());
    let runtime =
        PathBuf::from(std::env::var_os("VK_AG_NATIVE_RUNTIME").expect("pinned official runtime"));
    let expected = std::env::var("VK_AG_NATIVE_RUNTIME_SHA256").expect("runtime hash");
    let model = std::env::var("VK_AG_NATIVE_MODEL").expect("previously advertised exact model ID");
    let mut input = std::fs::File::open(&runtime).unwrap();
    let mut hash = Sha256::new();
    let mut buffer = [0; 65536];
    loop {
        let size = input.read(&mut buffer).unwrap();
        if size == 0 {
            break;
        }
        hash.update(&buffer[..size]);
    }
    assert_eq!(format!("{:x}", hash.finalize()), expected);
    let mut receipt_options = std::fs::OpenOptions::new();
    receipt_options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        receipt_options.mode(0o600);
    }
    let mut receipt = receipt_options
        .open(root.join("RESULT.private.jsonl"))
        .expect("fresh attempt required; never replay uncertain inference");
    let scratch = root.join("scratch");
    std::fs::create_dir(&scratch).unwrap();
    std::fs::create_dir(scratch.join("tmp")).unwrap();
    let marker = format!("VK_PROBE_{}", uuid::Uuid::new_v4().simple());
    std::fs::write(scratch.join("probe.txt"), &marker).unwrap();
    let approvals = Arc::new(DenyNative(AtomicUsize::new(0)));
    let mut env = ExecutionEnv::new(Default::default(), false, String::new());
    env.insert("BROWSER", "/bin/false");
    env.insert("TMPDIR", scratch.join("tmp").display().to_string());
    let mut identity = None;
    for (index, prompt) in [
        "This is a bounded integration test. Work only in the current directory. Read probe.txt using a tool, then request creation of denied.txt containing test. The approval handler will deny the edit. Respect denial: do not retry or use another tool to evade it. Reply with the exact token read from probe.txt and a brief statement of the denied result. Do not inspect other directories.",
        "Without any tools or file access, repeat the exact VK_PROBE token you read in the previous turn. This tests native conversation continuity. Do not invent a new token.",
    ].into_iter().enumerate() {
        writeln!(receipt, "{}", serde_json::json!({"phase":"before_prompt","prompt_number":index+1,"max_prompts":2})).unwrap();
        receipt.flush().unwrap();
        let harness = AcpAgentHarness::with_session_namespace("antigravity-acp").with_personal_auth().with_model(&model);
        let child = harness.spawn_supervised_with_command(
            &scratch, prompt.into(), identity.as_deref(),
            CommandParts::new(runtime.display().to_string(), vec!["--uid=".into()]),
            &env, Some(approvals.clone()),
        ).await.unwrap();
        let (ok, logs) = finish(child).await;
        let sid = logs.lines().find_map(|line| match serde_json::from_str::<AcpEvent>(line).ok()? {
            AcpEvent::SessionStart(id) => Some(id), _ => None,
        });
        let contains_marker = logs.contains(&marker);
        let denied_file_absent = !scratch.join("denied.txt").exists();
        let events: Vec<_> = logs.lines().filter_map(|line| serde_json::from_str::<AcpEvent>(line).ok()).collect();
        let errors: Vec<_> = events.iter().filter_map(|e| if let AcpEvent::Error(s) = e {Some(s.clone())} else {None}).collect();
        writeln!(receipt, "{}", serde_json::json!({"phase":"after_prompt","prompt_number":index+1,"success":ok,"contains_marker":contains_marker,"denied_file_absent":denied_file_absent,"approval_count":approvals.0.load(Ordering::SeqCst),"session_present":sid.is_some(),"sanitized_adapter_errors":errors})).unwrap();
        receipt.flush().unwrap();
        assert!(ok && contains_marker && denied_file_absent, "native turn failed; inspect private metrics, not raw auth output");
        if index == 0 {
            assert!(approvals.0.load(Ordering::SeqCst) > 0, "native permission denial was not exercised");
            identity = sid;
            assert!(identity.is_some());
        } else {
            assert_eq!(identity, sid, "native session identity changed");
        }
    }
    writeln!(
        receipt,
        "{}",
        serde_json::json!({"passed":true,"prompt_calls":2,"activation_changed":false})
    )
    .unwrap();
}

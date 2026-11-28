//! Explicit opt-in, existing-account acceptance. Never runs in ordinary CI.
use std::{
    io::{Read, Write},
    sync::atomic::{AtomicBool, AtomicUsize, Ordering},
};

use async_trait::async_trait;
use sha2::{Digest, Sha256};
use tokio::io::AsyncReadExt;
use workspace_utils::approvals::{ApprovalStatus, QuestionStatus};

use super::*;
use crate::{approvals::ExecutorApprovalError, executors::acp::AcpAgentHarness};

#[derive(Default)]
struct NativeApprovals {
    allowed: AtomicUsize,
    denied: AtomicUsize,
    hold: AtomicBool,
    waiting: AtomicBool,
}
#[async_trait]
impl ExecutorApprovalService for NativeApprovals {
    fn supports_interactive_approvals(&self) -> bool {
        true
    }
    async fn create_tool_approval(&self, title: &str) -> Result<String, ExecutorApprovalError> {
        // Only the first explicit file-creation request receives AllowOnce.
        // The disposable outer filesystem prevents writes to production paths.
        Ok(if matches!(
            title,
            "Run create_file?" | "Run write_file?" | "Run write_to_file?"
        ) {
            "write"
        } else {
            "deny"
        }
        .into())
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
        id: &str,
        cancel: CancellationToken,
    ) -> Result<ApprovalStatus, ExecutorApprovalError> {
        if self.hold.load(Ordering::SeqCst) {
            self.waiting.store(true, Ordering::SeqCst);
            cancel.cancelled().await;
            return Err(ExecutorApprovalError::Cancelled);
        }
        if id == "write"
            && self
                .allowed
                .compare_exchange(0, 1, Ordering::SeqCst, Ordering::SeqCst)
                .is_ok()
        {
            Ok(ApprovalStatus::Approved)
        } else {
            self.denied.fetch_add(1, Ordering::SeqCst);
            Ok(ApprovalStatus::Denied { reason: None })
        }
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

fn turn_result(logs: &str) -> (Option<String>, String, Vec<String>) {
    let events: Vec<_> = logs
        .lines()
        .filter_map(|line| serde_json::from_str::<AcpEvent>(line).ok())
        .collect();
    let identity = events.iter().find_map(|e| {
        if let AcpEvent::SessionStart(id) = e {
            Some(id.clone())
        } else {
            None
        }
    });
    // Native load can replay prior messages. Require a new assistant response
    // after this turn's User event, never merely old history or tool output.
    let start = events
        .iter()
        .rposition(|e| matches!(e, AcpEvent::User(_)))
        .unwrap_or(events.len());
    let response = events[start..]
        .iter()
        .filter_map(|e| match e {
            AcpEvent::Message(proto::ContentBlock::Text(text)) => Some(text.text.as_str()),
            _ => None,
        })
        .collect();
    let errors = events
        .iter()
        .filter_map(|e| {
            if let AcpEvent::Error(s) = e {
                Some(s.clone())
            } else {
                None
            }
        })
        .collect();
    (identity, response, errors)
}

#[tokio::test]
#[ignore = "Requires explicit account authorization, mounted scratch and at most two real prompts"]
async fn antigravity_native_write_approval_denial_resume_and_cancel() {
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
    let approvals = Arc::new(NativeApprovals::default());
    let mut env = ExecutionEnv::new(Default::default(), false, String::new());
    env.insert("BROWSER", "/bin/false");
    env.insert("TMPDIR", scratch.join("tmp").display().to_string());
    writeln!(
        receipt,
        "{}",
        serde_json::json!({"phase":"before_prompt","prompt_number":1,"max_prompts":2})
    )
    .unwrap();
    receipt.flush().unwrap();
    let harness = AcpAgentHarness::with_session_namespace("antigravity-acp")
        .with_personal_auth()
        .with_model(&model);
    let child = harness.spawn_supervised_with_command(
        &scratch,
        "Bounded integration test: work only in the current directory. Read probe.txt with view_file. Use the file-creation tool to create allowed.txt containing the exact token you read; this first creation will receive Allow once. Then request creation of denied.txt containing test; this second creation will be denied. Respect the denial without retry or alternative tools. Finally reply with the exact token and the outcomes. Do not inspect any other directories.".into(), None,
        CommandParts::new(runtime.display().to_string(), vec!["--uid=".into()]), &env, Some(approvals.clone()),
    ).await.unwrap();
    let (ok, logs) = finish(child).await;
    let (identity, response, errors) = turn_result(&logs);
    let contains_marker = response.contains(&marker);
    let allowed_file_matches =
        std::fs::read_to_string(scratch.join("allowed.txt")).is_ok_and(|s| s.trim() == marker);
    let denied_file_absent = !scratch.join("denied.txt").exists();
    let allowed = approvals.allowed.load(Ordering::SeqCst);
    let denied = approvals.denied.load(Ordering::SeqCst);
    writeln!(receipt, "{}", serde_json::json!({"phase":"after_prompt","prompt_number":1,"success":ok,"contains_marker":contains_marker,"allowed_file_matches":allowed_file_matches,"denied_file_absent":denied_file_absent,"allowed_count":allowed,"denied_count":denied,"session_present":identity.is_some(),"sanitized_adapter_errors":errors})).unwrap();
    receipt.flush().unwrap();
    assert!(
        ok && contains_marker
            && allowed_file_matches
            && denied_file_absent
            && allowed == 1
            && denied > 0
            && identity.is_some(),
        "native approval/denial failed"
    );
    approvals.hold.store(true, Ordering::SeqCst);
    writeln!(
        receipt,
        "{}",
        serde_json::json!({"phase":"before_prompt","prompt_number":2,"max_prompts":2})
    )
    .unwrap();
    receipt.flush().unwrap();
    let harness = AcpAgentHarness::with_session_namespace("antigravity-acp")
        .with_personal_auth()
        .with_model(&model);
    let child = harness.spawn_supervised_with_command(
        &scratch, "Native history and cancellation test: FIRST, without reading any file or using any tool, send an assistant text response repeating the exact VK_PROBE token from our previous turn. Send that text BEFORE requesting any tool. THEN request creation of cancelled.txt containing test. Approval will remain pending and the client will cancel this turn. Do not inspect files, retry or use alternative tools.".into(), identity.as_deref(),
        CommandParts::new(runtime.display().to_string(), vec!["--uid=".into()]),
        &env, Some(approvals.clone()),
    ).await.unwrap();
    let cancel = child.cancel.clone().unwrap();
    let finish = tokio::spawn(finish(child));
    let waiting = tokio::time::timeout(Duration::from_secs(90), async {
        while !approvals.waiting.load(Ordering::SeqCst) && !finish.is_finished() {
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    })
    .await
    .is_ok()
        && approvals.waiting.load(Ordering::SeqCst);
    let cancelled_at = std::time::Instant::now();
    cancel.cancel();
    let (ok, logs) = finish.await.unwrap();
    let elapsed = cancelled_at.elapsed().as_secs_f64();
    let cancelled = logs
        .lines()
        .filter_map(|line| serde_json::from_str::<AcpEvent>(line).ok())
        .any(|e| matches!(e, AcpEvent::Error(message) if message == "ACP execution cancelled"));
    let file_absent = !scratch.join("cancelled.txt").exists();
    let (resumed_identity, response, errors) = turn_result(&logs);
    let native_resume_matches = identity == resumed_identity && response.contains(&marker);
    writeln!(receipt, "{}", serde_json::json!({"phase":"after_prompt","prompt_number":2,"native_resume_matches":native_resume_matches,"sanitized_adapter_errors":errors,"permission_pending":waiting,"cancelled":cancelled,"success":ok,"file_absent":file_absent,"cancel_to_reaped_seconds":elapsed})).unwrap();
    receipt.flush().unwrap();
    assert!(
        native_resume_matches && waiting && !ok && cancelled && file_absent && elapsed < 5.0,
        "native cancellation failed"
    );
    writeln!(
        receipt,
        "{}",
        serde_json::json!({"passed":true,"prompt_calls":2,"activation_changed":false})
    )
    .unwrap();
}

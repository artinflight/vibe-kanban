use async_trait::async_trait;
use tokio::io::AsyncReadExt;
use workspace_utils::approvals::{ApprovalStatus, QuestionStatus};

use super::*;
use crate::{approvals::ExecutorApprovalError, executors::acp::AcpAgentHarness};

struct Deny;
#[async_trait]
impl ExecutorApprovalService for Deny {
    fn supports_interactive_approvals(&self) -> bool {
        true
    }
    async fn create_tool_approval(&self, _: &str) -> Result<String, ExecutorApprovalError> {
        Ok("synthetic".into())
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
        Ok(ApprovalStatus::Denied {
            reason: Some("fixture denial".into()),
        })
    }
    async fn wait_question_answer(
        &self,
        _: &str,
        _: CancellationToken,
    ) -> Result<QuestionStatus, ExecutorApprovalError> {
        Err(ExecutorApprovalError::ServiceUnavailable)
    }
}

fn env() -> ExecutionEnv {
    ExecutionEnv::new(Default::default(), false, String::new())
}
fn command(scenario: &str, trace: &Path) -> CommandParts {
    CommandParts::new(
        "/usr/bin/python3".into(),
        vec![
            format!(
                "{}/src/executors/acp/supervised/fixture.py",
                env!("CARGO_MANIFEST_DIR")
            ),
            scenario.into(),
            trace.display().to_string(),
        ],
    )
}
async fn start(
    dir: &Path,
    scenario: &str,
    session: Option<&str>,
    model: Option<&str>,
) -> Result<SpawnedChild, ExecutorError> {
    let mut harness = AcpAgentHarness::with_session_namespace("antigravity-acp");
    if let Some(model) = model {
        harness = harness.with_model(model);
    }
    harness
        .spawn_supervised_with_command(
            dir,
            "synthetic prompt".into(),
            session,
            command(scenario, &dir.join("trace")),
            &env(),
            Some(Arc::new(Deny)),
        )
        .await
}
async fn finish(mut child: SpawnedChild) -> (bool, String) {
    let mut stdout = child.child.inner().stdout.take().unwrap();
    let logs = tokio::spawn(async move {
        let mut s = String::new();
        stdout.read_to_string(&mut s).await.unwrap();
        s
    });
    let result =
        tokio::time::timeout(Duration::from_secs(8), child.exit_signal.take().unwrap()).await;
    let _ = child.child.kill().await;
    let _ = child.child.wait().await;
    let result = result
        .expect("fixture terminal signal timed out")
        .expect("terminal signal lost");
    (
        matches!(result, ExecutorExitResult::Success),
        tokio::time::timeout(Duration::from_secs(3), logs)
            .await
            .unwrap()
            .unwrap(),
    )
}
fn session(log: &str) -> String {
    log.lines()
        .find_map(|l| match serde_json::from_str::<AcpEvent>(l).ok()? {
            AcpEvent::SessionStart(id) => Some(id),
            _ => None,
        })
        .expect("session identity")
}

#[tokio::test]
async fn antigravity_acp_initializes_prompts_and_loads_namespaced_identity() {
    let dir = tempfile::tempdir().unwrap();
    let (ok, logs) = finish(
        start(dir.path(), "ok", None, Some("fixture-model"))
            .await
            .unwrap(),
    )
    .await;
    assert!(ok, "{logs}");
    assert!(logs.contains("fixture-ok"));
    let id = session(&logs);
    assert!(id.starts_with("antigravity-acp:v1:"));
    let (ok, resumed) = finish(start(dir.path(), "ok", Some(&id), None).await.unwrap()).await;
    assert!(ok, "{resumed}");
    assert_eq!(session(&resumed), id);
    let trace = std::fs::read_to_string(dir.path().join("trace")).unwrap();
    assert!(trace.contains("session/load"));
    assert!(trace.contains("session/set_model"));
    assert!(!trace.contains("authenticate"));
    let foreign = id.replacen("antigravity-acp", "gemini_sessions", 1);
    assert!(start(dir.path(), "ok", Some(&foreign), None).await.is_err());
    let other = tempfile::tempdir().unwrap();
    assert!(start(other.path(), "ok", Some(&id), None).await.is_err());
    let (ok, logs) = finish(start(dir.path(), "no-load", Some(&id), None).await.unwrap()).await;
    assert!(!ok);
    assert!(logs.contains("native resume is unsupported"));
}

#[tokio::test]
async fn antigravity_acp_denial_is_sent_without_automatic_feedback_prompt() {
    let dir = tempfile::tempdir().unwrap();
    let (ok, logs) = finish(start(dir.path(), "approval", None, None).await.unwrap()).await;
    assert!(ok, "{logs}");
    let trace = std::fs::read_to_string(dir.path().join("trace")).unwrap();
    assert!(trace.contains("reject-once"));
    assert_eq!(trace.matches("session/prompt").count(), 1);
}

#[tokio::test]
async fn antigravity_acp_cancel_sends_notification_and_fails_terminally() {
    let dir = tempfile::tempdir().unwrap();
    let child = start(dir.path(), "wait", None, None).await.unwrap();
    tokio::time::timeout(Duration::from_secs(3), async {
        while !std::fs::read_to_string(dir.path().join("trace"))
            .unwrap_or_default()
            .contains("session/prompt")
        {
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .unwrap();
    child.cancel.as_ref().unwrap().cancel();
    // Give the fixture time to observe the written cancellation before process cleanup.
    tokio::time::timeout(Duration::from_secs(3), async {
        while !std::fs::read_to_string(dir.path().join("trace"))
            .unwrap_or_default()
            .contains("session/cancel")
        {
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
    })
    .await
    .unwrap();
    let (ok, logs) = finish(child).await;
    assert!(!ok);
    assert!(logs.contains("cancelled"));
}

#[tokio::test]
async fn antigravity_acp_errors_and_unsupported_models_fail_without_fallback() {
    for scenario in [
        "malformed",
        "init-error",
        "wrong-version",
        "auth",
        "prompt-error",
        "cancelled",
        "no-models",
        "model-error",
    ] {
        let dir = tempfile::tempdir().unwrap();
        let model = if scenario == "no-models" || scenario == "model-error" {
            Some("fixture-model")
        } else {
            None
        };
        let (ok, logs) = finish(start(dir.path(), scenario, None, model).await.unwrap()).await;
        assert!(!ok, "{scenario}: {logs}");
        assert!(logs.contains("Error"), "{scenario}: {logs}");
        if !["prompt-error", "cancelled"].contains(&scenario) {
            assert!(
                !std::fs::read_to_string(dir.path().join("trace"))
                    .unwrap()
                    .contains("session/prompt")
            );
        }
    }
}

#[tokio::test]
async fn antigravity_acp_missing_runtime_or_approvals_never_launches() {
    let dir = tempfile::tempdir().unwrap();
    let harness = AcpAgentHarness::with_session_namespace("antigravity-acp");
    let missing = harness
        .spawn_supervised_with_command(
            dir.path(),
            "synthetic".into(),
            None,
            CommandParts::new(
                dir.path().join("absent-runtime").display().to_string(),
                vec![],
            ),
            &env(),
            Some(Arc::new(Deny)),
        )
        .await;
    assert!(matches!(
        missing,
        Err(ExecutorError::ExecutableNotFound { .. })
    ));
    for approvals in [
        None,
        Some(Arc::new(crate::approvals::NoopExecutorApprovalService)
            as Arc<dyn ExecutorApprovalService>),
    ] {
        assert!(
            harness
                .spawn_supervised_with_command(
                    dir.path(),
                    "synthetic".into(),
                    None,
                    command("ok", &dir.path().join("trace")),
                    &env(),
                    approvals
                )
                .await
                .is_err()
        );
    }
    assert!(!dir.path().join("trace").exists());
}

#[tokio::test]
async fn antigravity_acp_mode_override_is_rejected_before_launch() {
    let dir = tempfile::tempdir().unwrap();
    let error = AcpAgentHarness::with_session_namespace("antigravity-acp")
        .with_mode("unsupported-mode")
        .spawn_supervised_with_command(
            dir.path(),
            "synthetic".into(),
            None,
            command("ok", &dir.path().join("trace")),
            &env(),
            Some(Arc::new(Deny)),
        )
        .await
        .unwrap_err();
    assert!(error.to_string().contains("mode overrides are unsupported"));
    assert!(!dir.path().join("trace").exists());
}

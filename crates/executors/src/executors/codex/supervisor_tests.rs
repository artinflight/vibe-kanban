//! Scripted app-server boundary tests: no live account or native thread is used.
use std::{process::Stdio, sync::Arc};

use tokio::{io::AsyncReadExt, process::Command, sync::oneshot};
use tokio_util::sync::CancellationToken;

use super::{
    client::LogWriter,
    jsonrpc::{ExitSignalSender, JsonRpcPeer},
    *,
};

async fn launch(supervisor: bool, goal: &str) -> (bool, Vec<String>) {
    // Each request is also recorded on stderr. Any load/resume/turn call after
    // a denied goal is visible even if production code ignores its failure.
    let script = r#"
import json,sys
for line in sys.stdin:
    req=json.loads(line)
    method=req['method']
    print(method,file=sys.stderr,flush=True)
    if method=='account/read':
        result={'account':None,'requiresOpenaiAuth':False}
    elif method=='thread/goal/get':
        if sys.argv[1]=='rpc_error':
            print(json.dumps({'id':req['id'],'error':{'code':-32601,'message':'method not found'}}),flush=True)
            continue
        result=json.loads(sys.argv[1])
    else:
        print(json.dumps({'id':req['id'],'error':{'code':-1,'message':'test stops at resume'}}),flush=True)
        continue
    print(json.dumps({'id':req['id'],'result':result}),flush=True)
"#;
    let mut child = Command::new("python3")
        .arg("-u")
        .arg("-c")
        .arg(script)
        .arg(goal)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true)
        .spawn()
        .unwrap();
    let cancel = CancellationToken::new();
    let client = AppServerClient::new(
        LogWriter::new(tokio::io::sink()),
        None,
        false,
        false,
        crate::env::RepoContext::default(),
        false,
        String::new(),
        cancel.clone(),
    );
    let (exit, _) = oneshot::channel();
    let peer = JsonRpcPeer::spawn(
        child.stdin.take().unwrap(),
        child.stdout.take().unwrap(),
        client.clone(),
        ExitSignalSender::new(exit),
        cancel.clone(),
    );
    client.connect(peer);
    let result = tokio::time::timeout(
        std::time::Duration::from_secs(5),
        Codex::launch_codex_agent(
            ThreadStartParams::default(),
            Some("test-thread".into()),
            "original instruction".into(),
            Arc::clone(&client),
            supervisor,
        ),
    )
    .await
    .unwrap();
    cancel.cancel();
    child.kill().await.unwrap();
    let mut calls = String::new();
    child
        .stderr
        .take()
        .unwrap()
        .read_to_string(&mut calls)
        .await
        .unwrap();
    (result.is_err(), calls.lines().map(str::to_owned).collect())
}

#[tokio::test]
async fn supervisor_never_resumes_paused_unknown_malformed_or_unreadable_goals() {
    for goal in [
        r#"{"goal":{"threadId":"test-thread","objective":"task","createdAt":1,"status":"paused"}}"#,
        r#"{"goal":{"threadId":"test-thread","objective":"task","createdAt":1,"status":"future_state"}}"#,
        r#"{"goal":{"threadId":"wrong-thread","objective":"task","createdAt":1,"status":"complete"}}"#,
        r#"{"goal":{}}"#,
        r#"{}"#,
        "rpc_error",
    ] {
        let (failed, calls) = launch(true, goal).await;
        assert!(failed);
        assert_eq!(calls, vec!["account/read", "thread/goal/get"]);
    }
}

#[tokio::test]
async fn absent_or_complete_native_goal_allows_resume_after_read_and_raw_direct_skips_gate() {
    for goal in [
        r#"{"goal":null}"#,
        r#"{"goal":{"threadId":"test-thread","objective":"task","createdAt":1,"status":"complete"}}"#,
    ] {
        let (_, calls) = launch(true, goal).await;
        assert_eq!(
            calls,
            vec!["account/read", "thread/goal/get", "thread/resume"]
        );
    }
    let (_, calls) = launch(false, r#"{"goal":{"status":"paused"}}"#).await;
    assert_eq!(calls, vec!["account/read", "thread/resume"]);
}

#[tokio::test]
async fn supervisor_cannot_invoke_slash_controls_even_with_profile_env_overrides() {
    let codex: Codex = serde_json::from_value(serde_json::json!({})).unwrap();
    let mut env =
        crate::env::ExecutionEnv::new(crate::env::RepoContext::default(), false, String::new());
    env.supervisor_message = true;
    let overrides =
        std::collections::HashMap::from([("VK_SUPERVISOR_MESSAGE".into(), "false".into())]);
    let env = env.with_overrides(&overrides);
    for command in [
        "/goal resume",
        "/goal new objective",
        "/compact",
        "/fast on",
        "/init",
    ] {
        let result = codex
            .spawn_slash_command(
                std::path::Path::new("/nonexistent-supervisor-test"),
                command,
                Some("test-thread"),
                &env,
            )
            .await;
        assert!(
            matches!(result,Err(ref error) if error.to_string().contains("supervisor_message_cannot_invoke_session_controls"))
        );
    }
}

//! Opt-in completion hook. Publication policy and receipts live outside agent sources.
//! Disabled unless VK_TURN_GIT_PRESERVATION_CONFIG is explicitly set by the operator.
use std::{path::Path, process::Stdio};

use serde_json::{Value, json};
use tokio::{io::AsyncWriteExt, process::Command};

const HELPER: &str = include_str!("../../../scripts/preservation/turn_git.py");

pub fn enabled() -> bool {
    std::env::var_os("VK_TURN_GIT_PRESERVATION_CONFIG").is_some()
}

pub fn blocked(workspace: &str, turn: &str, reason: &str) -> Value {
    json!({"version": 2, "state": "blocked", "workspace": workspace,
        "turn": turn, "reason": reason})
}

pub fn verified(report: &Value) -> bool {
    report.get("version").and_then(Value::as_u64) == Some(2)
        && report.get("state").and_then(Value::as_str) == Some("verified")
}

pub fn changed(report: &Value) -> bool {
    report["repositories"]
        .as_array()
        .is_some_and(|repos| repos.iter().any(|repo| repo["receipt"]["changed"] == true))
}

pub fn message(report: &Value) -> String {
    let coverage = report["repositories"]
        .as_array()
        .map(|repositories| {
            repositories
                .iter()
                .map(|repo| {
                    let path = repo["path"].as_str().unwrap_or("unknown repository");
                    if let Some(commit) = repo["receipt"]["commit"].as_str() {
                        format!(
                            "\nRepository: {path}. Commit: {commit}. {}",
                            repo["receipt"]["pr"]["url"]
                                .as_str()
                                .unwrap_or("Exact base coverage; no new PR.")
                        )
                    } else {
                        format!("\nRepository: {path}. Remote coverage unverified.")
                    }
                })
                .collect::<String>()
        })
        .unwrap_or_default();
    format!(
        "Git preservation {}. Workspace: {}. Turn: {}. {}. Excluded files are not Git-protected.{}",
        report["state"].as_str().unwrap_or("blocked"),
        report["workspace"].as_str().unwrap_or("unknown"),
        report["turn"].as_str().unwrap_or("unknown"),
        report["reason"].as_str().unwrap_or("unverifiable receipt"),
        coverage,
    )
}

/// Verify that no remaining member of the owned Linux process group can write.
/// The caller captures the group ID at spawn; an exited leader's Child::id is insufficient.
/// This does not certify detached or operator processes; cutover requires an external fence.
pub fn group_quiescent(group_id: u32) -> bool {
    #[cfg(target_os = "linux")]
    {
        let Ok(entries) = std::fs::read_dir("/proc") else {
            return false;
        };
        for entry in entries {
            let Ok(entry) = entry else {
                return false;
            };
            if entry.file_name().to_string_lossy().parse::<u32>().is_err() {
                continue;
            }
            let text = match std::fs::read_to_string(entry.path().join("stat")) {
                Ok(text) => text,
                Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
                Err(_) => return false,
            };
            let Some((_, fields)) = text.rsplit_once(") ") else {
                return false;
            };
            let mut fields = fields.split_whitespace();
            let state = fields.next();
            let _parent = fields.next();
            let group = fields.next().and_then(|s| s.parse::<u32>().ok());
            if group.is_none() {
                return false;
            }
            if group == Some(group_id) && !matches!(state, Some("Z" | "X")) {
                return false;
            }
        }
        true
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = group_id;
        false
    }
}

pub async fn invoke(action: &str, request: Value) -> Value {
    let workspace = request["workspace"].as_str().unwrap_or("unknown");
    let turn = request["turn"].as_str().unwrap_or("unknown");
    let fail = |reason| blocked(workspace, turn, reason);
    let Some(config) = std::env::var_os("VK_TURN_GIT_PRESERVATION_CONFIG") else {
        return fail("preservation is not configured");
    };
    invoke_with_config(action, request, Path::new(&config)).await
}

async fn invoke_with_config(action: &str, request: Value, config: &Path) -> Value {
    let workspace = request["workspace"].as_str().unwrap_or("unknown");
    let turn = request["turn"].as_str().unwrap_or("unknown");
    let fail = |reason| blocked(workspace, turn, reason);
    if !config.is_absolute() {
        return fail("preservation policy must be an absolute external path");
    }
    let execution = async {
        let mut child = Command::new("python3")
            .args(["-I", "-B", "-c", HELPER, action, "--config"])
            .arg(config)
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .kill_on_drop(true)
            .spawn()?;
        let mut stdin = child
            .stdin
            .take()
            .ok_or_else(|| std::io::Error::other("helper stdin missing"))?;
        stdin.write_all(request.to_string().as_bytes()).await?;
        drop(stdin);
        child.wait_with_output().await
    };
    match execution.await {
        Ok(output) if output.stdout.len() <= 4 * 1024 * 1024 => {
            match serde_json::from_slice::<Value>(&output.stdout) {
                Ok(report)
                    if report["version"] == 2
                        && report["workspace"] == request["workspace"]
                        && report["turn"] == request["turn"]
                        && (!verified(&report) || output.status.success()) =>
                {
                    report
                }
                _ => fail("helper returned an invalid or unsuccessful receipt"),
            }
        }
        _ => fail("helper unavailable or receipt exceeds size limit; preservation remains pending"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn receipt_acceptance_is_fail_closed() {
        for report in [
            json!({}),
            json!({"state": "verified"}),
            json!({"version": 1, "state": "verified"}),
            json!({"version": 2, "state": "pending"}),
            blocked("workspace", "turn", "push failed"),
        ] {
            assert!(!verified(&report));
        }
        assert!(verified(&json!({"version": 2, "state": "verified"})));
    }

    #[test]
    fn blocked_message_names_workspace_and_reason_without_protection_claim() {
        let text = message(&blocked("workspace-123", "turn-456", "remote unavailable"));
        assert!(text.contains("blocked"));
        assert!(text.contains("workspace-123"));
        assert!(text.contains("remote unavailable"));
        assert!(text.contains("Excluded files are not Git-protected"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn live_fixture_group_is_not_quiescent() {
        use std::os::unix::process::CommandExt;
        let mut child = std::process::Command::new("sleep")
            .arg("10")
            .process_group(0)
            .spawn()
            .unwrap();
        let id = child.id();
        let live = group_quiescent(id);
        child.kill().unwrap();
        child.wait().unwrap();
        assert!(
            !live,
            "An owned process capable of writing must keep preservation blocked"
        );
        assert!(group_quiescent(id));
    }

    #[cfg(target_os = "linux")]
    #[tokio::test]
    async fn embedded_helper_persists_pending_and_blocks_unfinished_fixture() {
        let temp = tempfile::tempdir().unwrap();
        let repo = temp.path().join("repo");
        std::fs::create_dir(&repo).unwrap();
        for args in [
            vec!["init", "-q", "-b", "feat/fixture"],
            vec!["config", "user.name", "Fixture"],
            vec!["config", "user.email", "fixture@example.invalid"],
        ] {
            assert!(
                std::process::Command::new("git")
                    .args(args)
                    .current_dir(&repo)
                    .status()
                    .unwrap()
                    .success()
            );
        }
        std::fs::write(repo.join("source.txt"), "source fixture").unwrap();
        for args in [
            vec!["add", "source.txt"],
            vec![
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=/dev/null",
                "commit",
                "-qm",
                "fixture",
            ],
        ] {
            assert!(
                std::process::Command::new("git")
                    .args(args)
                    .current_dir(&repo)
                    .status()
                    .unwrap()
                    .success()
            );
        }
        let state = temp.path().join("state");
        std::fs::create_dir(&state).unwrap();
        let mount = std::process::Command::new("findmnt")
            .args(["-no", "TARGET", "--target"])
            .arg(&state)
            .output()
            .unwrap();
        assert!(mount.status.success());
        let mount = String::from_utf8(mount.stdout).unwrap().trim().to_string();
        let config = temp.path().join("policy.json");
        std::fs::write(
            &config,
            json!({"storage_mount": mount, "state_root": state, "repositories": {"repo": {
                "common_dir": repo.join(".git"), "allowed": ["source.txt"]
            }}})
            .to_string(),
        )
        .unwrap();
        let request = json!({"workspace":"fixture-workspace", "turn":"fixture-turn",
            "writers_fenced":true, "repositories":[{"id":"repo", "path":repo}]});
        let admitted = invoke_with_config("begin", request.clone(), &config).await;
        assert_eq!(admitted["state"], "pending", "{admitted}");
        assert!(state.join("fixture-workspace/fixture-turn.json").exists());
        let check = invoke_with_config("check", request, &config).await;
        assert_eq!(check["state"], "blocked", "{check}");
        assert!(check["reason"].as_str().unwrap().contains("pending"));
    }
}

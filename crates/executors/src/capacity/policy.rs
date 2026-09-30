//! Admission restrictions for unattended work. Verify the effective native
//! profile before activation; an ignored override must never grant execution.
use std::io;

use codex_app_server_protocol::{ThreadResumeParams, ThreadResumeResponse};
use serde_json::{Value, json};

use super::PreparedCapacity;
use crate::executors::{ExecutorError, codex::client::AppServerClient};

pub const DISABLED_FEATURES: &[&str] = &[
    "apps",
    "plugins",
    "remote_plugin",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "in_app_browser",
    "computer_use",
    "multi_agent",
    "multi_agent_v2",
    "skill_mcp_dependency_install",
    "request_permissions_tool",
];

fn invalid(message: &str) -> ExecutorError {
    ExecutorError::Io(io::Error::other(message))
}

pub fn verify_launcher(profile: Option<&str>, approved: &str) -> Result<(), ExecutorError> {
    if profile.is_some_and(|command| command.trim() != approved.trim()) {
        return Err(invalid(
            "Scheduled goals must use the service-approved local Codex launcher",
        ));
    }
    Ok(())
}

fn verify_scope(workspace: &std::path::Path, protected: &[&std::path::Path]) -> io::Result<()> {
    let workspace = std::fs::canonicalize(workspace)?;
    for path in protected {
        if std::fs::canonicalize(path)?.starts_with(&workspace) {
            return Err(io::Error::other(
                "Scheduled workspace overlaps execution authority or Codex state",
            ));
        }
    }
    Ok(())
}

// Service-level configuration only; a goal/profile cannot grant itself new paths.
fn build_roots(value: Option<&str>, protected: &[&std::path::Path]) -> io::Result<Vec<String>> {
    let paths: Vec<String> =
        serde_json::from_str(value.unwrap_or("[]")).map_err(io::Error::other)?;
    if paths.len() > 8 {
        return Err(io::Error::other(
            "At most eight scheduled build directories are supported",
        ));
    }
    let mut roots = Vec::new();
    for path in paths {
        let path = std::path::Path::new(&path);
        if !path.is_absolute() || !path.is_dir() {
            return Err(io::Error::other(
                "Scheduled build directories must exist and be absolute",
            ));
        }
        let path = std::fs::canonicalize(path)?;
        verify_scope(&path, protected)?;
        for authority in protected {
            if path.starts_with(std::fs::canonicalize(authority)?) {
                return Err(io::Error::other(
                    "Scheduled build directory overlaps execution authority",
                ));
            }
        }
        roots.push(path.to_string_lossy().into_owned());
    }
    roots.sort();
    roots.dedup();
    Ok(roots)
}

pub fn configured_build_roots(capacity: &PreparedCapacity) -> Result<Vec<String>, ExecutorError> {
    let home = crate::executors::codex::codex_home()
        .ok_or_else(|| invalid("Codex home is unavailable"))?;
    Ok(build_roots(
        std::env::var("VK_CAPACITY_BUILD_ROOTS").ok().as_deref(),
        &[
            capacity
                .file
                .parent()
                .ok_or_else(|| invalid("Missing permission directory"))?,
            &capacity.guard,
            &home,
        ],
    )?)
}

pub async fn resume(
    client: &AppServerClient,
    params: ThreadResumeParams,
    capacity: &PreparedCapacity,
) -> Result<ThreadResumeResponse, ExecutorError> {
    let lease = &capacity.lease;
    if params
        .config
        .as_ref()
        .is_some_and(|config| config.contains_key("profile"))
    {
        return Err(invalid(
            "Scheduled work cannot apply an unverified alternate Codex config profile",
        ));
    }
    let cwd = params
        .cwd
        .clone()
        .ok_or_else(|| invalid("Scheduled workspace is missing"))?;
    if !std::path::Path::new(&cwd).is_absolute() || cwd == "/" {
        return Err(invalid("Scheduled work needs a scoped local workspace"));
    }
    let home = crate::executors::codex::codex_home()
        .ok_or_else(|| invalid("Codex home is unavailable"))?;
    verify_scope(
        std::path::Path::new(&cwd),
        &[&capacity.file, &capacity.guard, &home],
    )?;
    let build_roots = configured_build_roots(capacity)?;
    let resolved = client
        .goal_request("config/read", json!({"cwd":cwd,"includeLayers":false}))
        .await?;
    let effective = resolved
        .get("config")
        .and_then(Value::as_object)
        .ok_or_else(|| invalid("Cannot verify scheduled configuration"))?;
    if effective
        .get("hooks")
        .is_some_and(|hooks| !hooks.is_null() && hooks != &json!({}))
    {
        return Err(invalid(
            "Scheduled execution does not support external lifecycle hooks",
        ));
    }
    let profile = format!("vk_capacity_{}", lease.id.replace('-', "_"));
    let mut wire = serde_json::to_value(params).map_err(io::Error::other)?;
    wire.as_object_mut().unwrap().remove("sandbox");
    wire["approvalPolicy"] = json!("never");
    wire["runtimeWorkspaceRoots"] = json!([cwd]);
    let config = wire
        .as_object_mut()
        .unwrap()
        .entry("config")
        .or_insert_with(|| json!({}));
    if config.is_null() {
        *config = json!({});
    }
    let config = config
        .as_object_mut()
        .ok_or_else(|| invalid("Invalid scheduled overrides"))?;
    config.insert("default_permissions".into(), json!(profile));
    config.insert("agents.max_depth".into(), json!(0));
    config.insert("agents.max_concurrent_threads_per_session".into(), json!(1));
    let mut filesystem = json!({"/":"read",":workspace_roots":{".":"write"}});
    for root in &build_roots {
        filesystem[root] = json!("write");
    }
    config.insert(format!("permissions.{profile}.filesystem"), filesystem);
    config.insert(
        format!("permissions.{profile}.network.enabled"),
        json!(false),
    );
    // Empty tables merge with inherited config. Disable each resolved entry.
    let servers = effective
        .get("mcp_servers")
        .and_then(Value::as_object)
        .ok_or_else(|| invalid("Cannot resolve scheduled MCP inventory"))?;
    config.insert(
        "mcp_servers".into(),
        Value::Object(
            servers
                .keys()
                .map(|name| (name.clone(), json!({"enabled":false})))
                .collect(),
        ),
    );
    for feature in DISABLED_FEATURES {
        config.insert(format!("features.{feature}"), json!(false));
    }
    let result = client.goal_request("thread/resume", wire).await?;
    verify_permissions(&result, &profile, &cwd, &build_roots)?;
    let provider = std::env::var("VK_CAPACITY_MODEL_PROVIDER").unwrap_or_else(|_| "openai".into());
    verify_provider(&result, &provider)?;
    let thread = result
        .pointer("/thread/id")
        .and_then(Value::as_str)
        .ok_or_else(|| invalid("Missing scheduled native thread"))?;
    let inventory = client
        .goal_request(
            "mcpServerStatus/list",
            json!({"threadId":thread,"limit":100}),
        )
        .await?;
    let entries = inventory
        .get("data")
        .and_then(Value::as_array)
        .ok_or_else(|| invalid("Cannot verify scheduled tool inventory"))?;
    if !inventory["nextCursor"].is_null()
        || entries
            .iter()
            .any(|entry| entry["runtimeStatus"] != "disabled")
    {
        return Err(invalid("Scheduled goals cannot use external MCP tools"));
    }
    serde_json::from_value(result)
        .map_err(|e| invalid(&format!("Invalid scheduled resume response: {e}")))
}

fn verify_provider(result: &Value, approved: &str) -> Result<(), ExecutorError> {
    if approved.is_empty() || result["modelProvider"] != approved {
        return Err(invalid(
            "Scheduled goal uses a model provider outside the supervised allowance",
        ));
    }
    Ok(())
}

fn verify_permissions(
    result: &Value,
    profile: &str,
    cwd: &str,
    build_roots: &[String],
) -> Result<(), ExecutorError> {
    if result
        .pointer("/activePermissionProfile/id")
        .and_then(Value::as_str)
        != Some(profile)
        || result["approvalPolicy"] != "never"
        || result["cwd"] != cwd
        || result["runtimeWorkspaceRoots"] != json!([cwd])
        || result.pointer("/sandbox/type").and_then(Value::as_str) != Some("workspaceWrite")
        || result.pointer("/sandbox/networkAccess") != Some(&json!(false))
        || result.pointer("/sandbox/excludeSlashTmp") != Some(&json!(true))
        || result.pointer("/sandbox/excludeTmpdirEnvVar") != Some(&json!(true))
        || result.pointer("/sandbox/writableRoots") != Some(&json!(build_roots))
    {
        return Err(invalid(
            "Native thread did not apply restricted scheduled permissions",
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn scheduled_profile_cannot_replace_the_supervised_launcher_or_provider() {
        verify_launcher(None, "codex").unwrap();
        verify_launcher(Some("codex"), "codex").unwrap();
        assert!(verify_launcher(Some("ssh remote codex"), "codex").is_err());
        verify_provider(&json!({"modelProvider":"openai"}), "openai").unwrap();
        assert!(verify_provider(&json!({"modelProvider":"other-account"}), "openai").is_err());
        assert!(verify_provider(&json!({}), "openai").is_err());
    }
    #[test]
    fn writable_workspace_cannot_include_authority_even_through_symlinks() {
        let root = std::env::temp_dir().join(format!("capacity-scope-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("work")).unwrap();
        std::fs::create_dir_all(root.join("private")).unwrap();
        std::fs::write(root.join("private/lease"), "permission").unwrap();
        verify_scope(&root.join("work"), &[&root.join("private/lease")]).unwrap();
        assert!(verify_scope(&root, &[&root.join("private/lease")]).is_err());
        #[cfg(unix)]
        {
            std::os::unix::fs::symlink(&root, root.join("alias")).unwrap();
            assert!(verify_scope(&root.join("alias"), &[&root.join("private/lease")]).is_err());
        }
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn build_directories_cannot_include_or_live_inside_authority() {
        let root = std::env::temp_dir().join(format!("capacity-build-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir_all(root.join("private/cache")).unwrap();
        std::fs::create_dir_all(root.join("build")).unwrap();
        for path in [
            root.clone(),
            root.join("private"),
            root.join("private/cache"),
        ] {
            let input = serde_json::to_string(&vec![path]).unwrap();
            assert!(build_roots(Some(&input), &[&root.join("private")]).is_err());
        }
        let input = serde_json::to_string(&vec![root.join("build")]).unwrap();
        assert_eq!(
            build_roots(Some(&input), &[&root.join("private")])
                .unwrap()
                .len(),
            1
        );
        assert!(build_roots(Some("[\"relative\"]"), &[]).is_err());
        assert!(build_roots(Some("{}"), &[]).is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
    #[test]
    fn ignored_or_broadened_native_permissions_fail_admission() {
        let valid = json!({"activePermissionProfile":{"id":"capacity"},"approvalPolicy":"never",
            "cwd":"/work","runtimeWorkspaceRoots":["/work"],"sandbox":{"type":"workspaceWrite",
            "networkAccess":false,"excludeSlashTmp":true,"excludeTmpdirEnvVar":true,"writableRoots":[]}});
        verify_permissions(&valid, "capacity", "/work", &[]).unwrap();
        for (pointer, value) in [
            ("/sandbox/networkAccess", json!(true)),
            ("/sandbox/writableRoots", json!(["/"])),
            ("/activePermissionProfile/id", json!(":danger-full-access")),
            ("/runtimeWorkspaceRoots", json!(["/work", "/"])),
            ("/sandbox/excludeSlashTmp", json!(false)),
            ("/approvalPolicy", json!("on-request")),
        ] {
            let mut changed = valid.clone();
            *changed.pointer_mut(pointer).unwrap() = value;
            assert!(
                verify_permissions(&changed, "capacity", "/work", &[]).is_err(),
                "{pointer}"
            );
        }
    }
}

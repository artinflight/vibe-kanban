use std::{
    process::Stdio,
    sync::{Arc, OnceLock},
};

use async_trait::async_trait;
use tokio::{io::AsyncWriteExt, sync::RwLock};
use utils::{self, command_ext::NoWindowExt};
use uuid::Uuid;

use crate::services::config::{Config, SoundFile};

/// Trait for sending push notifications. Implementations can use
/// platform-specific OS commands, Tauri's notification plugin, etc.
#[async_trait]
pub trait PushNotifier: Send + Sync + 'static {
    async fn send(&self, title: &str, message: &str, workspace_id: Option<Uuid>);
}

/// Global push notifier set before server startup (e.g., by the Tauri app).
/// Falls back to `DefaultPushNotifier` if not set.
static GLOBAL_PUSH_NOTIFIER: OnceLock<Arc<dyn PushNotifier>> = OnceLock::new();
static NTFY_CONFIG: OnceLock<Option<NtfyConfig>> = OnceLock::new();

/// Register a custom push notifier globally. Must be called before the server
/// starts (i.e., before `LocalDeployment::new()`). Typically called from the
/// Tauri app to inject a `TauriNotifier` that uses the native notification API.
pub fn set_global_push_notifier(notifier: Arc<dyn PushNotifier>) {
    let _ = GLOBAL_PUSH_NOTIFIER.set(notifier);
}

/// Get the global push notifier, or `DefaultPushNotifier` if none was set.
pub fn get_global_push_notifier() -> Arc<dyn PushNotifier> {
    GLOBAL_PUSH_NOTIFIER
        .get()
        .cloned()
        .unwrap_or_else(|| Arc::new(DefaultPushNotifier))
}

/// Default push notifier using platform-specific OS commands.
/// Used as a fallback when no Tauri app handle is available.
pub struct DefaultPushNotifier;

/// Cache for WSL root path from PowerShell
static WSL_ROOT_PATH_CACHE: OnceLock<Option<String>> = OnceLock::new();

#[derive(Clone, Debug)]
struct NtfyConfig {
    base_url: String,
    topic: String,
    bearer_token: Option<String>,
    tags: Option<String>,
    priority: Option<String>,
    ssh_destination: Option<String>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkspaceCompletionStatus {
    Completed,
    Failed,
}

const SUMMARY_METADATA_LABELS: &[&str] = &[
    "PR",
    "Docs",
    "Churn",
    "Human Needed",
    "Commit/Push",
    "Preview URL",
    "Branch",
    "Worktree",
];

#[async_trait]
impl PushNotifier for DefaultPushNotifier {
    async fn send(&self, title: &str, message: &str, _workspace_id: Option<Uuid>) {
        if cfg!(target_os = "macos") {
            send_macos_notification(title, message).await;
        } else if cfg!(target_os = "linux") && !utils::is_wsl2() {
            send_linux_notification(title, message).await;
        } else if cfg!(target_os = "windows") || (cfg!(target_os = "linux") && utils::is_wsl2()) {
            send_windows_notification(title, message).await;
        }
    }
}

/// Service for handling cross-platform notifications including sound alerts and push notifications
#[derive(Clone)]
pub struct NotificationService {
    config: Arc<RwLock<Config>>,
    push_notifier: Arc<dyn PushNotifier>,
}

impl std::fmt::Debug for NotificationService {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("NotificationService")
            .field("config", &self.config)
            .finish()
    }
}

impl NotificationService {
    pub fn new(config: Arc<RwLock<Config>>) -> Self {
        Self {
            config,
            push_notifier: get_global_push_notifier(),
        }
    }

    /// Send both sound and push notifications if enabled.
    /// `workspace_id` is forwarded to the push notifier so Tauri can emit a
    /// navigation event when the notification is clicked.
    pub async fn notify(&self, title: &str, message: &str, workspace_id: Option<Uuid>) {
        let config = self.config.read().await.notifications.clone();

        if config.sound_enabled {
            Self::play_sound_notification(&config.sound_file).await;
        }

        if config.push_enabled {
            self.push_notifier.send(title, message, workspace_id).await;
        }

        if let Some(ntfy) = ntfy_config() {
            ntfy.send(title, message).await;
        }
    }

    /// Play a system sound notification across platforms
    async fn play_sound_notification(sound_file: &SoundFile) {
        let file_path = match sound_file.get_path().await {
            Ok(path) => path,
            Err(e) => {
                tracing::error!("Failed to create cached sound file: {}", e);
                return;
            }
        };

        // Use platform-specific sound notification
        // Note: spawn() calls are intentionally not awaited - sound notifications should be fire-and-forget
        if cfg!(target_os = "macos") {
            let _ = tokio::process::Command::new("afplay")
                .arg(&file_path)
                .spawn();
        } else if cfg!(target_os = "linux") && !utils::is_wsl2() {
            // Try different Linux audio players
            if tokio::process::Command::new("paplay")
                .arg(&file_path)
                .spawn()
                .is_ok()
            {
                // Success with paplay
            } else if tokio::process::Command::new("aplay")
                .arg(&file_path)
                .spawn()
                .is_ok()
            {
                // Success with aplay
            } else {
                // Try system bell as fallback
                let _ = tokio::process::Command::new("echo")
                    .arg("-e")
                    .arg("\\a")
                    .spawn();
            }
        } else if cfg!(target_os = "windows") || (cfg!(target_os = "linux") && utils::is_wsl2()) {
            // Convert WSL path to Windows path if in WSL2
            let file_path = if utils::is_wsl2() {
                if let Some(windows_path) = wsl_to_windows_path(&file_path).await {
                    windows_path
                } else {
                    file_path.to_string_lossy().to_string()
                }
            } else {
                file_path.to_string_lossy().to_string()
            };

            let _ = tokio::process::Command::new("powershell.exe")
                .arg("-c")
                .arg(format!(
                    r#"(New-Object Media.SoundPlayer "{file_path}").PlaySync()"#
                ))
                .no_window()
                .spawn();
        }
    }
}

impl NtfyConfig {
    fn from_env() -> Option<Self> {
        let topic = std::env::var("VK_NTFY_TOPIC").ok()?.trim().to_string();
        if topic.is_empty() {
            return None;
        }

        let base_url = std::env::var("VK_NTFY_BASE_URL")
            .ok()
            .map(|value| value.trim().trim_end_matches('/').to_string())
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "http://127.0.0.1".to_string());

        let ssh_destination = std::env::var("VK_NTFY_SSH_DESTINATION")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty());

        Some(Self {
            base_url,
            topic,
            bearer_token: std::env::var("VK_NTFY_BEARER_TOKEN")
                .ok()
                .filter(|value| !value.trim().is_empty()),
            tags: std::env::var("VK_NTFY_TAGS")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty()),
            priority: std::env::var("VK_NTFY_PRIORITY")
                .ok()
                .map(|value| value.trim().to_string())
                .filter(|value| !value.is_empty()),
            ssh_destination,
        })
    }

    fn publish_url(&self) -> String {
        format!(
            "{}/{}",
            self.base_url.trim_end_matches('/'),
            self.topic.trim_start_matches('/')
        )
    }

    async fn send(&self, title: &str, message: &str) {
        if let Some(ssh_destination) = &self.ssh_destination {
            self.send_via_ssh(ssh_destination, title, message).await;
        } else {
            self.send_direct(title, message).await;
        }
    }

    async fn send_direct(&self, title: &str, message: &str) {
        let client = reqwest::Client::new();
        let mut request = client
            .post(self.publish_url())
            .header("Title", sanitize_header_value(title))
            .header("Content-Type", "text/plain; charset=utf-8");

        if let Some(priority) = &self.priority {
            request = request.header("Priority", sanitize_header_value(priority));
        }

        if let Some(tags) = &self.tags {
            request = request.header("Tags", sanitize_header_value(tags));
        }

        if let Some(token) = &self.bearer_token {
            request = request.bearer_auth(token);
        }

        if let Err(error) = request.body(message.to_string()).send().await {
            tracing::warn!("Failed to publish ntfy notification: {}", error);
        }
    }

    async fn send_via_ssh(&self, ssh_destination: &str, title: &str, message: &str) {
        let mut command = tokio::process::Command::new("ssh");
        command
            .arg(ssh_destination)
            .arg("curl")
            .arg("-fsS")
            .arg("-X")
            .arg("POST")
            .arg("-H")
            .arg(format!("Title: {}", sanitize_header_value(title)))
            .arg("-H")
            .arg("Content-Type: text/plain; charset=utf-8");

        if let Some(priority) = &self.priority {
            command
                .arg("-H")
                .arg(format!("Priority: {}", sanitize_header_value(priority)));
        }

        if let Some(tags) = &self.tags {
            command
                .arg("-H")
                .arg(format!("Tags: {}", sanitize_header_value(tags)));
        }

        if let Some(token) = &self.bearer_token {
            command.arg("-H").arg(format!(
                "Authorization: Bearer {}",
                sanitize_header_value(token)
            ));
        }

        command
            .arg("--data-binary")
            .arg("@-")
            .arg(self.publish_url())
            .stdin(Stdio::piped())
            .stdout(Stdio::null())
            .stderr(Stdio::piped());

        let mut child = match command.spawn() {
            Ok(child) => child,
            Err(error) => {
                tracing::warn!("Failed to spawn SSH ntfy publisher: {}", error);
                return;
            }
        };

        if let Some(mut stdin) = child.stdin.take()
            && let Err(error) = stdin.write_all(message.as_bytes()).await
        {
            tracing::warn!("Failed to write ntfy payload to SSH stdin: {}", error);
            let _ = child.start_kill();
            return;
        }

        match child.wait_with_output().await {
            Ok(output) if output.status.success() => {}
            Ok(output) => {
                let stderr = String::from_utf8_lossy(&output.stderr);
                tracing::warn!(
                    "SSH ntfy publisher exited with status {}: {}",
                    output.status,
                    stderr.trim()
                );
            }
            Err(error) => {
                tracing::warn!("Failed waiting for SSH ntfy publisher: {}", error);
            }
        }
    }
}

fn ntfy_config() -> Option<&'static NtfyConfig> {
    NTFY_CONFIG.get_or_init(NtfyConfig::from_env).as_ref()
}

fn sanitize_header_value(value: &str) -> String {
    value.replace(['\r', '\n'], " ")
}

pub fn extract_summary_metadata(summary: &str) -> Vec<(String, String)> {
    summary
        .lines()
        .filter_map(|line| {
            let (label, value) = line.split_once("::")?;
            let label = label.trim();
            if !SUMMARY_METADATA_LABELS.contains(&label) {
                return None;
            }

            let value = value.trim();
            if value.is_empty() {
                return None;
            }

            Some((label.to_string(), value.to_string()))
        })
        .collect()
}

pub fn format_workspace_completion_message(
    workspace_name: &str,
    branch: &str,
    executor: Option<&str>,
    status: WorkspaceCompletionStatus,
    summary: Option<&str>,
) -> String {
    let status_value = match status {
        WorkspaceCompletionStatus::Completed => "Completed",
        WorkspaceCompletionStatus::Failed => "Failed",
    };

    let mut lines = vec![
        format!("Status: {status_value}"),
        format!("Workspace: {workspace_name}"),
        format!("Branch: {branch}"),
    ];

    if let Some(executor) = executor.filter(|value| !value.trim().is_empty()) {
        lines.push(format!("Executor: {executor}"));
    }

    let metadata = summary.map(extract_summary_metadata).unwrap_or_default();
    if !metadata.is_empty() {
        lines.push(String::new());
        lines.extend(
            metadata
                .into_iter()
                .map(|(label, value)| format!("{label}:: {value}")),
        );
    }

    lines.join("\n")
}

// --- Platform-specific push notification helpers (used by DefaultPushNotifier) ---

/// Send macOS notification using osascript
async fn send_macos_notification(title: &str, message: &str) {
    let script = format!(
        r#"display notification "{message}" with title "{title}" sound name "Glass""#,
        message = message.replace('"', r#"\""#),
        title = title.replace('"', r#"\""#)
    );

    let _ = tokio::process::Command::new("osascript")
        .arg("-e")
        .arg(script)
        .spawn();
}

/// Send Linux notification using notify-rust
async fn send_linux_notification(title: &str, message: &str) {
    use notify_rust::Notification;

    let title = title.to_string();
    let message = message.to_string();

    let _handle = tokio::task::spawn_blocking(move || {
        match Notification::new()
            .summary(&title)
            .body(&message)
            .timeout(10000)
            .show()
        {
            Ok(_) => {}
            Err(e) => {
                let err_str = e.to_string();
                if err_str.contains("ServiceUnknown")
                    || err_str.contains("org.freedesktop.Notifications")
                {
                    tracing::warn!("Linux notification daemon not available: {}", e);
                } else {
                    tracing::warn!("Failed to send Linux notification: {}", e);
                }
            }
        }
    });
    drop(_handle); // Don't await, fire-and-forget
}

/// Send Windows/WSL notification using PowerShell toast script
async fn send_windows_notification(title: &str, message: &str) {
    let script_path = match utils::get_powershell_script().await {
        Ok(path) => path,
        Err(e) => {
            tracing::error!("Failed to get PowerShell script: {}", e);
            return;
        }
    };

    // Convert WSL path to Windows path if in WSL2
    let script_path_str = if utils::is_wsl2() {
        if let Some(windows_path) = wsl_to_windows_path(&script_path).await {
            windows_path
        } else {
            script_path.to_string_lossy().to_string()
        }
    } else {
        script_path.to_string_lossy().to_string()
    };

    let _ = tokio::process::Command::new("powershell.exe")
        .arg("-NoProfile")
        .arg("-ExecutionPolicy")
        .arg("Bypass")
        .arg("-File")
        .arg(script_path_str)
        .arg("-Title")
        .arg(title)
        .arg("-Message")
        .arg(message)
        .no_window()
        .spawn();
}

#[cfg(test)]
mod tests {
    use super::{
        WorkspaceCompletionStatus, extract_summary_metadata, format_workspace_completion_message,
    };

    #[test]
    fn extracts_ops_playbook_metadata_lines() {
        let summary = r#"Validation
Ran the relevant checks.

What changed
Added ntfy notifications.

Why it matters
Operators get completion alerts.

What's next
Set the env vars and verify a run.

PR:: Not opened yet
Docs:: Current
Churn:: No
Human Needed:: Yes
Commit/Push:: Local only
Preview URL:: Not Generated
Branch:: vk/a80a-vk-wire-ntfy
Worktree:: /tmp/worktree"#;

        let metadata = extract_summary_metadata(summary);
        assert_eq!(metadata.len(), 8);
        assert_eq!(
            metadata[0],
            ("PR".to_string(), "Not opened yet".to_string())
        );
        assert_eq!(
            metadata[7],
            ("Worktree".to_string(), "/tmp/worktree".to_string())
        );
    }

    #[test]
    fn formats_workspace_completion_message_with_metadata() {
        let message = format_workspace_completion_message(
            "Wire Ntfy",
            "vk/a80a-vk-wire-ntfy",
            Some("codex"),
            WorkspaceCompletionStatus::Completed,
            Some(
                "What's next\nReady for verification.\n\nPR:: Not opened yet\nBranch:: vk/a80a-vk-wire-ntfy",
            ),
        );

        assert!(message.contains("Workspace: Wire Ntfy"));
        assert!(message.contains("Executor: codex"));
        assert!(message.contains("PR:: Not opened yet"));
        assert!(message.contains("Branch:: vk/a80a-vk-wire-ntfy"));
    }
}

/// Get WSL root path via PowerShell (cached)
async fn get_wsl_root_path() -> Option<String> {
    if let Some(cached) = WSL_ROOT_PATH_CACHE.get() {
        return cached.clone();
    }

    match tokio::process::Command::new("powershell.exe")
        .arg("-c")
        .arg("(Get-Location).Path -replace '^.*::', ''")
        .current_dir("/")
        .no_window()
        .output()
        .await
    {
        Ok(output) => {
            match String::from_utf8(output.stdout) {
                Ok(pwd_str) => {
                    let pwd = pwd_str.trim();
                    tracing::info!("WSL root path detected: {}", pwd);

                    // Cache the result
                    let _ = WSL_ROOT_PATH_CACHE.set(Some(pwd.to_string()));
                    return Some(pwd.to_string());
                }
                Err(e) => {
                    tracing::error!("Failed to parse PowerShell pwd output as UTF-8: {}", e);
                }
            }
        }
        Err(e) => {
            tracing::error!("Failed to execute PowerShell pwd command: {}", e);
        }
    }

    // Cache the failure result
    let _ = WSL_ROOT_PATH_CACHE.set(None);
    None
}

/// Convert WSL path to Windows UNC path for PowerShell
async fn wsl_to_windows_path(wsl_path: &std::path::Path) -> Option<String> {
    let path_str = wsl_path.to_string_lossy();

    // Relative paths work fine as-is in PowerShell
    if !path_str.starts_with('/') {
        tracing::debug!("Using relative path as-is: {}", path_str);
        return Some(path_str.to_string());
    }

    // Get cached WSL root path from PowerShell
    if let Some(wsl_root) = get_wsl_root_path().await {
        // Simply concatenate WSL root with the absolute path - PowerShell doesn't mind /
        let windows_path = format!("{wsl_root}{path_str}");
        tracing::debug!("WSL path converted: {} -> {}", path_str, windows_path);
        Some(windows_path)
    } else {
        tracing::error!(
            "Failed to determine WSL root path for conversion: {}",
            path_str
        );
        None
    }
}

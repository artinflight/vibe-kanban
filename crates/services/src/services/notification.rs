use std::{
    env,
    sync::{Arc, OnceLock},
};

use async_trait::async_trait;
use db::models::execution_process::ExecutionProcessStatus;
use tokio::sync::RwLock;
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
    }

    /// Send the standard workspace completion notification and, when configured,
    /// mirror the final turn metadata to ntfy via the homelab SSH host.
    pub async fn notify_workspace_turn_completion(
        &self,
        workspace_name: &str,
        status: &ExecutionProcessStatus,
        summary: Option<&str>,
        workspace_id: Uuid,
    ) {
        let title = workspace_completion_title(workspace_name, status);
        let message = build_workspace_completion_message(workspace_name, status, summary);
        let config = self.config.read().await.notifications.clone();

        if config.sound_enabled {
            Self::play_sound_notification(&config.sound_file).await;
        }

        if config.push_enabled {
            self.push_notifier
                .send(&title, &message, Some(workspace_id))
                .await;

            if let Some(ntfy) = TurnCompletionNtfyConfig::from_env() {
                ntfy.publish(title, message).await;
            }
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

#[derive(Debug, Clone)]
struct TurnCompletionNtfyConfig {
    ssh_host: String,
    container: String,
    topic: String,
}

impl TurnCompletionNtfyConfig {
    fn from_env() -> Option<Self> {
        let topic = env::var("VK_NTFY_TOPIC")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())?;

        let ssh_host = env::var("VK_NTFY_SSH_HOST")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "homelab".to_string());

        let container = env::var("VK_NTFY_CONTAINER")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "ntfy".to_string());

        Some(Self {
            ssh_host,
            container,
            topic,
        })
    }

    async fn publish(&self, title: String, message: String) {
        let ssh_host = self.ssh_host.clone();
        let container = self.container.clone();
        let topic = self.topic.clone();

        let handle = tokio::spawn(async move {
            match tokio::process::Command::new("ssh")
                .arg(&ssh_host)
                .arg("docker")
                .arg("exec")
                .arg(&container)
                .arg("ntfy")
                .arg("publish")
                .arg("--quiet")
                .arg("--markdown")
                .arg("--title")
                .arg(&title)
                .arg("--message")
                .arg(&message)
                .arg(&topic)
                .output()
                .await
            {
                Ok(output) if output.status.success() => {}
                Ok(output) => {
                    tracing::warn!(
                        host = %ssh_host,
                        container = %container,
                        topic = %topic,
                        status = %output.status,
                        stderr = %String::from_utf8_lossy(&output.stderr),
                        "failed to publish workspace completion to ntfy"
                    );
                }
                Err(error) => {
                    tracing::warn!(
                        host = %ssh_host,
                        container = %container,
                        topic = %topic,
                        ?error,
                        "failed to execute ntfy publish command"
                    );
                }
            }
        });

        drop(handle);
    }
}

fn workspace_completion_title(workspace_name: &str, status: &ExecutionProcessStatus) -> String {
    match status {
        ExecutionProcessStatus::Completed => format!("Workspace Complete: {workspace_name}"),
        ExecutionProcessStatus::Failed => format!("Workspace Failed: {workspace_name}"),
        ExecutionProcessStatus::Killed => format!("Workspace Stopped: {workspace_name}"),
        ExecutionProcessStatus::Running => format!("Workspace Running: {workspace_name}"),
    }
}

fn build_workspace_completion_message(
    workspace_name: &str,
    status: &ExecutionProcessStatus,
    summary: Option<&str>,
) -> String {
    let mut lines = vec![format!("Workspace:: {workspace_name}")];
    let metadata_lines = summary
        .map(extract_summary_metadata_lines)
        .unwrap_or_default();

    if metadata_lines.is_empty() {
        lines.push(format!("Status:: {}", workspace_status_label(status)));
    } else {
        lines.extend(metadata_lines);
    }

    lines.join("\n")
}

fn extract_summary_metadata_lines(summary: &str) -> Vec<String> {
    summary
        .lines()
        .filter_map(|line| {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                return None;
            }

            let normalized = trimmed.strip_prefix("- ").unwrap_or(trimmed).trim();
            let (label, value) = normalized.split_once("::")?;
            let label = label.trim();
            let value = value.trim();

            if label.is_empty() || value.is_empty() {
                return None;
            }

            Some(format!("{label}:: {value}"))
        })
        .collect()
}

fn workspace_status_label(status: &ExecutionProcessStatus) -> &'static str {
    match status {
        ExecutionProcessStatus::Completed => "Completed",
        ExecutionProcessStatus::Failed => "Failed",
        ExecutionProcessStatus::Killed => "Killed",
        ExecutionProcessStatus::Running => "Running",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn extracts_summary_metadata_lines_from_compact_block() {
        let summary = r#"Validation
Checks passed.

What changed
Updated the notifier.

Why it matters
Turn completion now reaches ntfy.

What's next
Branch is ready for verification.

PR:: Not opened yet
Docs:: Not Current
Churn:: No
Human Needed:: Yes
Commit/Push:: Not committed and Not pushed
Preview URL:: Not Generated
Branch:: vk/wire-ntfy
Worktree:: /tmp/vk"#;

        assert_eq!(
            extract_summary_metadata_lines(summary),
            vec![
                "PR:: Not opened yet",
                "Docs:: Not Current",
                "Churn:: No",
                "Human Needed:: Yes",
                "Commit/Push:: Not committed and Not pushed",
                "Preview URL:: Not Generated",
                "Branch:: vk/wire-ntfy",
                "Worktree:: /tmp/vk",
            ]
        );
    }

    #[test]
    fn workspace_completion_message_falls_back_when_summary_has_no_metadata() {
        let message = build_workspace_completion_message(
            "demo-workspace",
            &ExecutionProcessStatus::Completed,
            Some("Plain summary without metadata."),
        );

        assert_eq!(message, "Workspace:: demo-workspace\nStatus:: Completed");
    }
}

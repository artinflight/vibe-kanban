use std::{
    env,
    sync::{Arc, OnceLock},
    time::Duration,
};

use async_trait::async_trait;
use db::models::execution_process::ExecutionProcessStatus;
use tokio::sync::{RwLock, mpsc};
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
    turn_completion_ntfy: Option<TurnCompletionNtfyPublisher>,
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
            turn_completion_ntfy: TurnCompletionNtfyPublisher::from_env(),
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
    /// mirror a bounded turn-completion notice to ntfy.
    pub async fn notify_workspace_turn_completion(
        &self,
        workspace_name: &str,
        status: &ExecutionProcessStatus,
        agent_label: Option<&str>,
        summary: Option<&str>,
        workspace_id: Uuid,
    ) {
        let notice = TurnCompletionNotice {
            workspace_name,
            status,
            agent_label,
            summary,
        };
        let title = workspace_completion_title(workspace_name, status);
        let message = build_workspace_completion_message(&notice);
        let config = self.config.read().await.notifications.clone();

        if config.sound_enabled {
            Self::play_sound_notification(&config.sound_file).await;
        }

        if config.push_enabled {
            self.push_notifier
                .send(&title, &message, Some(workspace_id))
                .await;
        }

        if let Some(ntfy) = &self.turn_completion_ntfy {
            ntfy.publish(title, message);
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

#[derive(Debug, Clone, PartialEq, Eq)]
struct NtfyTurnCompletionConfig {
    publish_url: Url,
    token: Option<String>,
    timeout: Duration,
}

impl NtfyTurnCompletionConfig {
    fn from_env() -> Option<Self> {
        Self::from_lookup(|key| std::env::var(key).ok())
    }

    fn from_lookup(mut lookup: impl FnMut(&str) -> Option<String>) -> Option<Self> {
        let url = env_first(&mut lookup, &["VK_TURN_COMPLETION_NTFY_URL", "VK_NTFY_URL"])?;
        let topic = env_first(
            &mut lookup,
            &["VK_TURN_COMPLETION_NTFY_TOPIC", "VK_NTFY_TOPIC"],
        )?;
        let token = env_first(
            &mut lookup,
            &["VK_TURN_COMPLETION_NTFY_TOKEN", "VK_NTFY_TOKEN"],
        );
        let timeout = env_first(&mut lookup, &["VK_TURN_COMPLETION_NTFY_TIMEOUT_SECS"])
            .and_then(|value| value.parse::<u64>().ok())
            .filter(|seconds| *seconds > 0)
            .map(Duration::from_secs)
            .unwrap_or_else(|| Duration::from_secs(4));

        let publish_url = build_ntfy_publish_url(&url, &topic)?;

        Some(Self {
            publish_url,
            token,
            timeout,
        })
    }
}

fn env_first(lookup: &mut impl FnMut(&str) -> Option<String>, keys: &[&str]) -> Option<String> {
    keys.iter()
        .filter_map(|key| lookup(key))
        .map(|value| value.trim().to_string())
        .find(|value| !value.is_empty())
}

fn build_ntfy_publish_url(base_url: &str, topic: &str) -> Option<Url> {
    let mut url = match Url::parse(base_url.trim()) {
        Ok(url) => url,
        Err(err) => {
            tracing::warn!("Invalid ntfy URL '{}': {}", base_url, err);
            return None;
        }
    };

    {
        let mut path_segments = match url.path_segments_mut() {
            Ok(segments) => segments,
            Err(()) => {
                tracing::warn!("ntfy URL cannot be used as a base URL: {}", base_url);
                return None;
            }
        };
        path_segments.pop_if_empty();
        for segment in topic.trim_matches('/').split('/') {
            if !segment.is_empty() {
                path_segments.push(segment);
            }
        }
    }

    Some(url)
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

#[cfg(test)]
mod tests {
    use std::{collections::HashMap, time::Duration};

    use super::{NtfyTurnCompletionConfig, build_ntfy_publish_url};

    #[test]
    fn builds_ntfy_publish_url_without_duplicate_slashes() {
        let url = build_ntfy_publish_url("https://opntfy.fly.dev/", "/vk-workspace-turns/")
            .expect("valid ntfy URL");

        assert_eq!(url.as_str(), "https://opntfy.fly.dev/vk-workspace-turns");
    }

    #[test]
    fn reads_turn_completion_env_before_generic_ntfy_env() {
        let values = HashMap::from([
            ("VK_NTFY_URL", "https://generic.example"),
            ("VK_NTFY_TOPIC", "generic-topic"),
            ("VK_NTFY_TOKEN", "generic-token"),
            ("VK_TURN_COMPLETION_NTFY_URL", "https://turns.example"),
            ("VK_TURN_COMPLETION_NTFY_TOPIC", "turn-topic"),
            ("VK_TURN_COMPLETION_NTFY_TOKEN", "turn-token"),
            ("VK_TURN_COMPLETION_NTFY_TIMEOUT_SECS", "7"),
        ]);

        let config = NtfyTurnCompletionConfig::from_lookup(|key| {
            values.get(key).map(|value| value.to_string())
        })
        .expect("configured ntfy");

        assert_eq!(
            config.publish_url.as_str(),
            "https://turns.example/turn-topic"
        );
        assert_eq!(config.token.as_deref(), Some("turn-token"));
        assert_eq!(config.timeout, Duration::from_secs(7));
    }

    #[test]
    fn supports_generic_ntfy_env_as_fallback() {
        let values = HashMap::from([
            ("VK_NTFY_URL", "https://opntfy.fly.dev"),
            ("VK_NTFY_TOPIC", "vk-workspace-turns"),
        ]);

        let config = NtfyTurnCompletionConfig::from_lookup(|key| {
            values.get(key).map(|value| value.to_string())
        })
        .expect("configured ntfy");

        assert_eq!(
            config.publish_url.as_str(),
            "https://opntfy.fly.dev/vk-workspace-turns"
        );
        assert_eq!(config.token, None);
        assert_eq!(config.timeout, Duration::from_secs(4));
    }
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

#[derive(Clone)]
struct TurnCompletionNtfyPublisher {
    tx: mpsc::Sender<TurnCompletionNtfyMessage>,
}

#[derive(Debug)]
struct TurnCompletionNtfyMessage {
    title: String,
    body: String,
}

#[derive(Debug, Clone)]
struct TurnCompletionNtfyConfig {
    base_url: String,
    topic: String,
    token: Option<String>,
    queue_capacity: usize,
    timeout: Duration,
}

impl TurnCompletionNtfyConfig {
    fn from_env() -> Option<Self> {
        Self::from_env_reader(env_var_trimmed)
    }

    fn from_env_reader(mut read: impl FnMut(&str) -> Option<String>) -> Option<Self> {
        let topic = match read("VK_TURN_COMPLETION_NTFY_TOPIC") {
            Some(value) => value,
            None => read("VK_NTFY_TOPIC")?,
        };
        let base_url = read("VK_TURN_COMPLETION_NTFY_URL")
            .or_else(|| read("VK_NTFY_URL"))
            .unwrap_or_else(|| "https://ntfy.sh".to_string());
        let token = read("VK_TURN_COMPLETION_NTFY_TOKEN").or_else(|| read("VK_NTFY_TOKEN"));
        let queue_capacity = read("VK_TURN_COMPLETION_NTFY_QUEUE")
            .and_then(|value| value.parse::<usize>().ok())
            .unwrap_or(64)
            .clamp(1, 1024);
        let timeout = Duration::from_secs(
            read("VK_TURN_COMPLETION_NTFY_TIMEOUT_SECS")
                .and_then(|value| value.parse::<u64>().ok())
                .unwrap_or(4)
                .clamp(1, 30),
        );

        Some(Self {
            base_url,
            topic,
            token,
            queue_capacity,
            timeout,
        })
    }

    fn endpoint(&self) -> String {
        format!(
            "{}/{}",
            self.base_url.trim_end_matches('/'),
            self.topic.trim_start_matches('/')
        )
    }
}

impl TurnCompletionNtfyPublisher {
    fn from_env() -> Option<Self> {
        let config = TurnCompletionNtfyConfig::from_env()?;
        let client = match reqwest::Client::builder().timeout(config.timeout).build() {
            Ok(client) => client,
            Err(error) => {
                tracing::warn!(?error, "failed to initialize ntfy client");
                return None;
            }
        };
        let (tx, rx) = mpsc::channel(config.queue_capacity);

        if let Ok(handle) = tokio::runtime::Handle::try_current() {
            handle.spawn(run_ntfy_publisher(client, config, rx));
        } else {
            tracing::warn!("ntfy notifications disabled because no Tokio runtime is active");
            return None;
        }

        Some(Self { tx })
    }

    fn publish(&self, title: String, body: String) {
        match self.tx.try_send(TurnCompletionNtfyMessage { title, body }) {
            Ok(()) => {}
            Err(mpsc::error::TrySendError::Full(_)) => {
                tracing::warn!("dropping ntfy turn-completion notice because the queue is full");
            }
            Err(mpsc::error::TrySendError::Closed(_)) => {
                tracing::warn!("dropping ntfy turn-completion notice because the worker stopped");
            }
        }
    }
}

async fn run_ntfy_publisher(
    client: reqwest::Client,
    config: TurnCompletionNtfyConfig,
    mut rx: mpsc::Receiver<TurnCompletionNtfyMessage>,
) {
    while let Some(message) = rx.recv().await {
        publish_ntfy_message(&client, &config, message).await;
    }
}

async fn publish_ntfy_message(
    client: &reqwest::Client,
    config: &TurnCompletionNtfyConfig,
    message: TurnCompletionNtfyMessage,
) {
    let mut request = client
        .post(config.endpoint())
        .header("Title", message.title)
        .header("Markdown", "yes")
        .body(message.body);

    if let Some(token) = &config.token {
        request = request.bearer_auth(token);
    }

    match request.send().await {
        Ok(response) if response.status().is_success() => {}
        Ok(response) => {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            tracing::warn!(
                status = %status,
                body = %truncate_for_log(&body),
                topic = %config.topic,
                base_url = %config.base_url,
                "failed to publish workspace completion to ntfy"
            );
        }
        Err(error) => {
            tracing::warn!(
                ?error,
                topic = %config.topic,
                base_url = %config.base_url,
                "failed to execute ntfy publish request"
            );
        }
    }
}

fn env_var_trimmed(name: &str) -> Option<String> {
    env::var(name)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn workspace_completion_title(workspace_name: &str, status: &ExecutionProcessStatus) -> String {
    match status {
        ExecutionProcessStatus::Completed => format!("VK turn complete: {workspace_name}"),
        ExecutionProcessStatus::Failed => format!("VK turn failed: {workspace_name}"),
        ExecutionProcessStatus::Killed => format!("VK turn stopped: {workspace_name}"),
        ExecutionProcessStatus::Running => format!("VK turn running: {workspace_name}"),
    }
}

struct TurnCompletionNotice<'a> {
    workspace_name: &'a str,
    status: &'a ExecutionProcessStatus,
    agent_label: Option<&'a str>,
    summary: Option<&'a str>,
}

fn build_workspace_completion_message(notice: &TurnCompletionNotice<'_>) -> String {
    let mut lines = vec![
        format!("Workspace:: {}", notice.workspace_name),
        format!("Status:: {}", workspace_status_label(notice.status)),
    ];

    if let Some(agent_label) = notice.agent_label.and_then(non_empty_trimmed) {
        lines.push(format!("Agent:: {agent_label}"));
    }

    let final_statement = notice
        .summary
        .and_then(non_empty_trimmed)
        .map(brief_final_statement)
        .unwrap_or_else(|| "No final assistant statement was captured.".to_string());
    lines.push(format!("Final:: {final_statement}"));

    lines.join("\n")
}

fn brief_final_statement(summary: &str) -> String {
    let normalized = summary
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .take(6)
        .collect::<Vec<_>>()
        .join(" ");

    truncate_chars(&normalized, 700)
}

fn non_empty_trimmed(value: &str) -> Option<&str> {
    let trimmed = value.trim();
    if trimmed.is_empty() {
        None
    } else {
        Some(trimmed)
    }
}

fn truncate_chars(value: &str, max_chars: usize) -> String {
    if value.chars().count() <= max_chars {
        return value.to_string();
    }

    let mut out = value
        .chars()
        .take(max_chars.saturating_sub(3))
        .collect::<String>();
    out.push_str("...");
    out
}

fn truncate_for_log(value: &str) -> String {
    truncate_chars(value, 500)
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
    fn workspace_completion_message_uses_brief_final_statement() {
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

        let notice = TurnCompletionNotice {
            workspace_name: "VK::Wire ntfy",
            status: &ExecutionProcessStatus::Completed,
            agent_label: Some("codex:gpt-5.5-high"),
            summary: Some(summary),
        };

        assert_eq!(
            build_workspace_completion_message(&notice),
            "Workspace:: VK::Wire ntfy\nStatus:: Completed\nAgent:: codex:gpt-5.5-high\nFinal:: Validation Checks passed. What changed Updated the notifier. Why it matters Turn completion now reaches ntfy."
        );
    }

    #[test]
    fn workspace_completion_message_falls_back_when_summary_has_no_metadata() {
        let notice = TurnCompletionNotice {
            workspace_name: "demo-workspace",
            status: &ExecutionProcessStatus::Completed,
            agent_label: None,
            summary: None,
        };
        let message = build_workspace_completion_message(&notice);

        assert_eq!(
            message,
            "Workspace:: demo-workspace\nStatus:: Completed\nFinal:: No final assistant statement was captured."
        );
    }

    #[test]
    fn ntfy_endpoint_joins_base_url_and_topic() {
        let config = TurnCompletionNtfyConfig {
            base_url: "https://opntfy.fly.dev/".to_string(),
            topic: "/vk-workspace-turns".to_string(),
            token: Some("token".to_string()),
            queue_capacity: 64,
            timeout: Duration::from_secs(4),
        };

        assert_eq!(
            config.endpoint(),
            "https://opntfy.fly.dev/vk-workspace-turns"
        );
    }

    #[test]
    fn turn_completion_ntfy_config_prefers_specific_env_names() {
        let vars = [
            ("VK_TURN_COMPLETION_NTFY_TOPIC", "vk-turns"),
            ("VK_TURN_COMPLETION_NTFY_URL", "https://ntfy.example"),
            ("VK_TURN_COMPLETION_NTFY_TOKEN", "secret"),
            ("VK_TURN_COMPLETION_NTFY_QUEUE", "12"),
            ("VK_TURN_COMPLETION_NTFY_TIMEOUT_SECS", "2"),
            ("VK_NTFY_TOPIC", "legacy-topic"),
            ("VK_NTFY_URL", "https://legacy.example"),
            ("VK_NTFY_TOKEN", "legacy-secret"),
        ];
        let config = TurnCompletionNtfyConfig::from_env_reader(|key| {
            vars.iter()
                .find_map(|(name, value)| (*name == key).then(|| (*value).to_string()))
        })
        .expect("config");

        assert_eq!(config.endpoint(), "https://ntfy.example/vk-turns");
        assert_eq!(config.token.as_deref(), Some("secret"));
        assert_eq!(config.queue_capacity, 12);
        assert_eq!(config.timeout, Duration::from_secs(2));
    }
}

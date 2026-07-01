use std::{
    sync::{Arc, OnceLock},
    time::Duration,
};

use async_trait::async_trait;
use reqwest::{StatusCode, header};
use tokio::sync::RwLock;
use url::Url;
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

    /// Publish coding-agent turn completion to ntfy when configured.
    ///
    /// Supported env vars:
    /// - VK_TURN_COMPLETION_NTFY_URL, VK_TURN_COMPLETION_NTFY_TOPIC,
    ///   VK_TURN_COMPLETION_NTFY_TOKEN, VK_TURN_COMPLETION_NTFY_TIMEOUT_SECS
    /// - VK_NTFY_URL, VK_NTFY_TOPIC, VK_NTFY_TOKEN as fallbacks
    pub async fn notify_turn_completion_ntfy(&self, title: &str, message: &str) {
        let Some(config) = NtfyTurnCompletionConfig::from_env() else {
            return;
        };

        let client = match reqwest::Client::builder().timeout(config.timeout).build() {
            Ok(client) => client,
            Err(err) => {
                tracing::warn!("Failed to build ntfy client: {}", err);
                return;
            }
        };

        let mut request = client
            .post(config.publish_url.clone())
            .header("Title", title)
            .header("Tags", "computer")
            .header("Priority", "default")
            .body(message.to_string());

        if let Some(token) = config.token.as_deref() {
            let value = format!("Bearer {token}");
            match header::HeaderValue::from_str(&value) {
                Ok(value) => {
                    request = request.header(header::AUTHORIZATION, value);
                }
                Err(err) => {
                    tracing::warn!("Ignoring invalid ntfy authorization header: {}", err);
                }
            }
        }

        match request.send().await {
            Ok(response) if response.status().is_success() => {}
            Ok(response) => {
                let status = response.status();
                tracing::warn!(
                    "ntfy turn-completion notification failed with status {}",
                    status
                );
                if status == StatusCode::UNAUTHORIZED || status == StatusCode::FORBIDDEN {
                    tracing::warn!("ntfy rejected the configured turn-completion credentials");
                }
            }
            Err(err) => {
                tracing::warn!(
                    "Failed to publish ntfy turn-completion notification: {}",
                    err
                );
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

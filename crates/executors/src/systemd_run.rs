use std::{collections::HashMap, path::Path, process::Stdio};

use command_group::AsyncGroupChild;
use tokio::process::Command;
use uuid::Uuid;
use workspace_utils::command_ext::GroupSpawnNoWindowExt;

#[derive(Clone, Copy)]
pub enum StdinMode {
    Null,
    Piped,
}

pub fn enabled() -> bool {
    let value = std::env::var("VK_USE_SYSTEMD_RUN")
        .or_else(|_| std::env::var("VK_LAB_USE_SYSTEMD_RUN"))
        .unwrap_or_default();
    matches!(
        value.trim().to_ascii_lowercase().as_str(),
        "1" | "true" | "yes" | "on"
    )
}

fn env_value(primary: &str, fallback: &str) -> Option<String> {
    std::env::var(primary)
        .ok()
        .filter(|v| !v.trim().is_empty())
        .or_else(|| {
            std::env::var(fallback)
                .ok()
                .filter(|v| !v.trim().is_empty())
        })
}

pub fn build_unit_name(prefix: &str) -> String {
    let cleaned = prefix
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '-' | '_') {
                c.to_ascii_lowercase()
            } else {
                '-'
            }
        })
        .collect::<String>()
        .trim_matches('-')
        .to_string();
    let cleaned = if cleaned.is_empty() {
        "exec".to_string()
    } else {
        cleaned
    };
    format!("vk-exec-{cleaned}-{}.service", Uuid::new_v4().simple())
}

pub fn spawn_transient_unit(
    unit_name: &str,
    description: &str,
    current_dir: &Path,
    program: &Path,
    args: &[String],
    env_vars: &HashMap<String, String>,
    stdin_mode: StdinMode,
) -> std::io::Result<AsyncGroupChild> {
    spawn_transient_unit_inner(
        unit_name,
        description,
        current_dir,
        program,
        args,
        env_vars,
        stdin_mode,
        None,
    )
}

#[allow(clippy::too_many_arguments)]
pub fn spawn_capacity_unit(
    unit_name: &str,
    current_dir: &Path,
    program: &Path,
    args: &[String],
    env_vars: &HashMap<String, String>,
    capacity: &crate::capacity::PreparedCapacity,
) -> std::io::Result<AsyncGroupChild> {
    spawn_transient_unit_inner(
        unit_name,
        "VK scheduled capacity execution",
        current_dir,
        program,
        args,
        env_vars,
        StdinMode::Piped,
        Some(capacity),
    )
}

#[allow(clippy::too_many_arguments)]
fn spawn_transient_unit_inner(
    unit_name: &str,
    description: &str,
    current_dir: &Path,
    program: &Path,
    args: &[String],
    env_vars: &HashMap<String, String>,
    stdin_mode: StdinMode,
    capacity: Option<&crate::capacity::PreparedCapacity>,
) -> std::io::Result<AsyncGroupChild> {
    let mut command = Command::new("systemd-run");
    command
        .kill_on_drop(true)
        .arg("--user")
        .arg("--pipe")
        .arg("--collect")
        .arg("--quiet")
        .arg("--service-type=exec")
        .arg("--unit")
        .arg(unit_name)
        .arg("--working-directory")
        .arg(current_dir)
        .arg("--description")
        .arg(description);

    if let Some(value) = env_value("VK_TRANSIENT_MEMORY_HIGH", "VK_LAB_TRANSIENT_MEMORY_HIGH") {
        command.arg(format!("--property=MemoryHigh={value}"));
    }
    if let Some(value) = env_value("VK_TRANSIENT_MEMORY_MAX", "VK_LAB_TRANSIENT_MEMORY_MAX") {
        command.arg(format!("--property=MemoryMax={value}"));
    }

    for (key, value) in env_vars {
        command.arg(format!("--setenv={key}={value}"));
    }

    if let Some(capacity) = capacity {
        let now = crate::capacity::wall_ms();
        capacity
            .lease
            .validate(now)
            .map_err(std::io::Error::other)?;
        // RuntimeMaxSec is relative to actual service start, so also arm an
        // absolute realtime kill timer BEFORE spawning. Startup delay or a
        // stalled guard must not move the immutable deadline into fresh quota.
        let runtime_ms = capacity
            .lease
            .stop_at_ms
            .saturating_sub(now)
            .saturating_sub(2000);
        if runtime_ms < 1000 {
            return Err(std::io::Error::other("Capacity deadline is too close"));
        }
        let kill_at = capacity.lease.stop_at_ms.saturating_sub(500);
        let timer = std::process::Command::new("systemd-run")
            .args(["--user", "--quiet", "--collect"])
            .arg(format!(
                "--unit={}-deadline",
                unit_name.trim_end_matches(".service")
            ))
            .arg(format!("--on-calendar=@{}", kill_at / 1000))
            .arg("--timer-property=AccuracySec=100ms")
            .arg("--timer-property=Persistent=true")
            .args([
                "/usr/bin/systemctl",
                "--user",
                "kill",
                "--kill-whom=all",
                "--signal=KILL",
                unit_name,
            ])
            .output()?;
        if !timer.status.success() {
            return Err(std::io::Error::other(
                "Could not arm independent capacity deadline",
            ));
        }
        command
            .arg(format!("--property=RuntimeMaxSec={}ms", runtime_ms))
            .arg("--property=TimeoutStopSec=1s")
            .arg("--property=KillMode=control-group")
            .arg("--property=Restart=no")
            .arg(&capacity.guard)
            .arg(&capacity.file);
    }
    command.arg(program);
    command.args(args);

    match stdin_mode {
        StdinMode::Null => {
            command.stdin(Stdio::null());
        }
        StdinMode::Piped => {
            command.stdin(Stdio::piped());
        }
    }

    command.stdout(Stdio::piped()).stderr(Stdio::piped());

    command.group_spawn_no_window()
}

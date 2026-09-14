use std::{
    fs,
    io::{self, Write},
    path::PathBuf,
};

use capacity_guard::Lease;
use serde::{Deserialize, Serialize};
use ts_rs::TS;
pub mod controller;

/// A persisted launch request is valid only in the VK process which issued it.
/// Restart reconciliation must obtain a new grant, never replay an old action.
pub fn issuer_epoch() -> &'static str {
    static EPOCH: std::sync::OnceLock<String> = std::sync::OnceLock::new();
    EPOCH.get_or_init(|| uuid::Uuid::new_v4().to_string())
}

/// Internal persisted executor action metadata. The authenticated scheduling
/// route constructs this; ordinary follow-ups never carry background authority.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, TS)]
pub struct CapacityExecution {
    pub issuer_epoch: String,
    pub id: String,
    pub allocation_id: String,
    pub expires_at_ms: u64,
    pub stop_at_ms: u64,
    pub lease_file: String,
    pub guard_binary: String,
}

#[derive(Debug, Clone)]
pub struct PreparedCapacity {
    pub file: PathBuf,
    pub guard: PathBuf,
    pub lease: Lease,
}

pub fn wall_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis() as u64
}

pub fn unit_name(execution: uuid::Uuid) -> String {
    format!("vk-capacity-{}.service", execution.simple())
}

impl CapacityExecution {
    /// Bind to the actual process UUID before starting any model work. File
    /// creation is exclusive: retrying an action cannot replay old permission.
    pub fn prepare(&self, execution_id: &str) -> io::Result<PreparedCapacity> {
        if self.issuer_epoch != issuer_epoch() {
            return Err(io::Error::other(
                "Capacity permission predates this VK process",
            ));
        }
        if !crate::systemd_run::enabled() {
            return Err(io::Error::other(
                "Background capacity requires systemd containment",
            ));
        }
        uuid::Uuid::parse_str(execution_id).map_err(io::Error::other)?;
        let guard = PathBuf::from(&self.guard_binary);
        let file = PathBuf::from(&self.lease_file);
        if !guard.is_absolute() || !guard.is_file() || !file.is_absolute() {
            return Err(io::Error::other(
                "Capacity guard and permission paths must be absolute",
            ));
        }
        let lease = Lease {
            version: 1,
            id: self.id.clone(),
            allocation_id: self.allocation_id.clone(),
            execution_id: execution_id.into(),
            expires_at_ms: self.expires_at_ms,
            stop_at_ms: self.stop_at_ms,
            sequence: 0,
            revoked: false,
        };
        lease.validate(wall_ms()).map_err(io::Error::other)?;
        let mut options = fs::OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        {
            use std::os::unix::fs::OpenOptionsExt;
            options.mode(0o600);
        }
        let mut handle = options.open(&file)?;
        handle.write_all(&serde_json::to_vec(&lease)?)?;
        handle.sync_all()?;
        fs::File::open(
            file.parent()
                .ok_or_else(|| io::Error::other("Missing capacity directory"))?,
        )?
        .sync_all()?;
        Ok(PreparedCapacity { file, guard, lease })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn persisted_request_from_previous_vk_process_cannot_launch() {
        let request = CapacityExecution {
            issuer_epoch: uuid::Uuid::new_v4().to_string(),
            id: uuid::Uuid::new_v4().to_string(),
            allocation_id: "old-week:day".into(),
            expires_at_ms: wall_ms() + 30_000,
            stop_at_ms: wall_ms() + 120_000,
            lease_file: "/unused-permission-path".into(),
            guard_binary: "/unused-guard-path".into(),
        };
        let restored: CapacityExecution =
            serde_json::from_str(&serde_json::to_string(&request).unwrap()).unwrap();
        let error = restored
            .prepare(&uuid::Uuid::new_v4().to_string())
            .unwrap_err();
        assert!(error.to_string().contains("predates this VK process"));
    }
}

//! Quota-independent execution fence. CU decides allowance; this guard only
//! accepts bounded permission, and cannot infer or create fresh allowance.
use std::{fs, io, path::Path};

use serde::{Deserialize, Serialize};

pub const MAX_LEASE_MS: u64 = 60_000;
pub const MAX_RUN_MS: u64 = 24 * 60 * 60 * 1000;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
pub struct Lease {
    pub version: u32,
    pub id: String,
    pub allocation_id: String,
    pub execution_id: String,
    pub expires_at_ms: u64,
    pub stop_at_ms: u64,
    pub sequence: u64,
    pub revoked: bool,
}

impl Lease {
    pub fn validate(&self, wall_ms: u64) -> Result<(), &'static str> {
        if self.version != 1
            || self.id.is_empty()
            || self.execution_id.is_empty()
            || self.allocation_id.is_empty()
            || self.id.len() > 128
            || self.execution_id.len() > 128
            || self.allocation_id.len() > 512
        {
            return Err("invalid permission identity");
        }
        if self.revoked {
            return Err("permission revoked");
        }
        if self.expires_at_ms <= wall_ms || self.stop_at_ms <= wall_ms {
            return Err("permission expired");
        }
        if self.expires_at_ms > self.stop_at_ms
            || self.expires_at_ms - wall_ms > MAX_LEASE_MS
            || self.stop_at_ms - wall_ms > MAX_RUN_MS
        {
            return Err("permission exceeds allowed lifetime");
        }
        Ok(())
    }
}

pub struct Fence {
    lease: Lease,
    monotonic_expiry: u64,
    monotonic_stop: u64,
    last_wall: u64,
    last_monotonic: u64,
    stopped: bool,
}

impl Fence {
    pub fn new(lease: Lease, wall_ms: u64, monotonic_ms: u64) -> Result<Self, &'static str> {
        lease.validate(wall_ms)?;
        Ok(Self {
            monotonic_expiry: monotonic_ms + lease.expires_at_ms - wall_ms,
            monotonic_stop: monotonic_ms + lease.stop_at_ms - wall_ms,
            last_wall: wall_ms,
            last_monotonic: monotonic_ms,
            lease,
            stopped: false,
        })
    }

    /// Once rejected, a fence is permanently closed. Even a newer lease cannot
    /// renew after expiry or change the allocation/execution/hard deadline.
    pub fn observe(
        &mut self,
        next: &Lease,
        wall_ms: u64,
        monotonic_ms: u64,
    ) -> Result<(), &'static str> {
        let result = self.check(next, wall_ms, monotonic_ms);
        if result.is_err() {
            self.stopped = true;
        }
        result
    }

    fn check(&mut self, next: &Lease, wall_ms: u64, monotonic_ms: u64) -> Result<(), &'static str> {
        if self.stopped {
            return Err("permission already stopped");
        }
        if monotonic_ms < self.last_monotonic
            || wall_ms < self.last_wall
            || wall_ms
                .saturating_sub(self.last_wall)
                .abs_diff(monotonic_ms.saturating_sub(self.last_monotonic))
                > 5000
        {
            return Err("clock changed; fresh execution required");
        }
        if wall_ms >= self.lease.expires_at_ms
            || monotonic_ms >= self.monotonic_expiry
            || wall_ms >= self.lease.stop_at_ms
            || monotonic_ms >= self.monotonic_stop
        {
            return Err("permission expired");
        }
        next.validate(wall_ms)?;
        if next.id != self.lease.id
            || next.execution_id != self.lease.execution_id
            || next.allocation_id != self.lease.allocation_id
            || next.stop_at_ms != self.lease.stop_at_ms
            || next.sequence < self.lease.sequence
            || (next.sequence == self.lease.sequence && next != &self.lease)
        {
            return Err("permission fence changed");
        }
        if next.sequence > self.lease.sequence {
            self.monotonic_expiry = monotonic_ms + next.expires_at_ms - wall_ms;
            self.lease = next.clone();
        }
        self.last_wall = wall_ms;
        self.last_monotonic = monotonic_ms;
        Ok(())
    }
}

pub fn read_lease(file: &Path) -> io::Result<Lease> {
    use std::io::Read;
    #[cfg(unix)]
    use std::os::unix::fs::{MetadataExt, OpenOptionsExt};
    let mut options = fs::OpenOptions::new();
    options.read(true);
    #[cfg(unix)]
    options.custom_flags(libc::O_NOFOLLOW | libc::O_NONBLOCK);
    let handle = options.open(file)?;
    let metadata = handle.metadata()?;
    if !metadata.is_file() || metadata.len() > 8192 {
        return Err(io::Error::other("permission must be a small regular file"));
    }
    #[cfg(unix)]
    if metadata.mode() & 0o077 != 0 || metadata.uid() != unsafe { libc::geteuid() } {
        return Err(io::Error::other(
            "permission file must be private and owned by this user",
        ));
    }
    let mut bytes = Vec::new();
    handle.take(8193).read_to_end(&mut bytes)?;
    if bytes.len() > 8192 {
        return Err(io::Error::other("permission file too large"));
    }
    serde_json::from_slice(&bytes).map_err(io::Error::other)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn lease() -> Lease {
        Lease {
            version: 1,
            id: "lease".into(),
            allocation_id: "old-week:day".into(),
            execution_id: "execution".into(),
            expires_at_ms: 20_000,
            stop_at_ms: 100_000,
            sequence: 0,
            revoked: false,
        }
    }
    #[test]
    fn expiry_cannot_be_resurrected() {
        let mut fence = Fence::new(lease(), 1000, 0).unwrap();
        let mut next = lease();
        next.sequence = 1;
        next.expires_at_ms = 40_000;
        assert!(fence.observe(&next, 20_000, 19_000).is_err());
        assert!(fence.observe(&next, 20_001, 19_001).is_err());
    }
    #[test]
    fn timely_renewals_still_stop_at_original_deadline() {
        let mut fence = Fence::new(lease(), 1000, 0).unwrap();
        let mut next = lease();
        for now in (10_000..100_000).step_by(10_000) {
            next.sequence += 1;
            next.expires_at_ms = (now + 20_000).min(100_000);
            fence.observe(&next, now, now - 1000).unwrap();
        }
        assert!(fence.observe(&next, 100_000, 99_000).is_err());
    }
    #[test]
    fn changed_cycle_execution_deadline_sequence_or_revocation_stops() {
        for field in 0..6 {
            let mut fence = Fence::new(lease(), 1000, 0).unwrap();
            let mut next = lease();
            match field {
                0 => next.allocation_id = "fresh-week".into(),
                1 => next.execution_id = "other".into(),
                2 => next.stop_at_ms += 1000,
                3 => next.expires_at_ms += 1000,
                4 => next.revoked = true,
                _ => next.id = "other".into(),
            }
            assert!(fence.observe(&next, 2000, 1000).is_err());
        }
    }
    #[test]
    fn clock_adjustments_fail_closed() {
        let mut fence = Fence::new(lease(), 1000, 0).unwrap();
        assert!(fence.observe(&lease(), 999, 100).is_err());
        let mut fence = Fence::new(lease(), 1000, 0).unwrap();
        assert!(fence.observe(&lease(), 9000, 100).is_err());
    }
    #[test]
    fn invalid_or_unbounded_permissions_are_rejected() {
        for field in 0..5 {
            let mut next = lease();
            match field {
                0 => next.expires_at_ms = 1000,
                1 => next.expires_at_ms = 99_000,
                2 => next.stop_at_ms = MAX_RUN_MS + 2000,
                3 => next.version = 2,
                _ => next.allocation_id.clear(),
            }
            assert!(Fence::new(next, 1000, 0).is_err());
        }
    }
}

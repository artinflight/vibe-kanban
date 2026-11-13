//! Consumer requirements for a trusted readiness authority. This is NOT a new Git
//! inventory/capture protocol and cannot fabricate successful owner admission.
use super::*;
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Scope {
    pub authority_contract: String,
    pub workspace_id: String,
    pub execution_id: String,
    pub snapshot_receipt: String,
    pub repository_inventory: String,
    pub head_inventory: String,
    pub owner_generation: String,
    pub effective_permissions: String,
    pub authorized_actions: String,
    pub toolchain: String,
    pub qualification_version: String,
    pub catalog_version: String,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Receipt {
    pub authority_contract: String,
    pub source_receipt: String,
    pub scope: Scope,
    pub observed_at_ms: u64,
    pub valid_until_ms: u64,
    /// Precise authority-owned failure codes; missing evidence never becomes [].
    pub blockers: Vec<String>,
    pub preservation_verified: bool,
    pub exclusive_owner_verified: bool,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum Readiness {
    Blocked {
        code: String,
        action: String,
        provider_started: bool,
    },
    Ready {
        receipt: String,
    },
    Hold {
        reason: String,
    },
}
pub fn check(receipt: Option<&Receipt>, expected: &Scope, now: u64) -> Readiness {
    let hold = |reason: &str| Readiness::Hold {
        reason: reason.into(),
    };
    let Some(r) = receipt else {
        return hold("readiness_authority_unavailable");
    };
    if !r.blockers.is_empty() {
        return hold(&format!("readiness_blocked:{}", r.blockers.join(",")));
    }
    if !present(&r.authority_contract)
        || !present(&r.source_receipt)
        || !r.preservation_verified
        || !r.exclusive_owner_verified
    {
        return hold("preservation_or_ownership_unverified");
    }
    if &r.scope != expected || r.authority_contract != expected.authority_contract {
        return hold("readiness_dependencies_changed");
    }
    if [
        &expected.authority_contract,
        &expected.workspace_id,
        &expected.execution_id,
        &expected.snapshot_receipt,
        &expected.repository_inventory,
        &expected.head_inventory,
        &expected.owner_generation,
        &expected.effective_permissions,
        &expected.authorized_actions,
        &expected.toolchain,
        &expected.qualification_version,
        &expected.catalog_version,
    ]
    .iter()
    .any(|v| !present(v))
    {
        return hold("readiness_dependency_missing");
    }
    if r.observed_at_ms > now || now >= r.valid_until_ms {
        return hold("readiness_stale");
    }
    Readiness::Ready {
        receipt: r.source_receipt.clone(),
    }
}
/// /usage-fetch throttling concerns metadata freshness, NOT generation exhaustion.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct UsageFetch {
    pub identity: Identity,
    pub source_receipt: String,
    pub observed_at_ms: u64,
    pub retry_at_ms: Option<u64>,
    pub throttled: bool,
}
impl UsageFetch {
    pub fn next_refresh(&self, attempt: u8, now: u64) -> Option<u64> {
        if !present(&self.source_receipt) || self.observed_at_ms > now {
            return None;
        }
        refresh_deadline(attempt, now, self.retry_at_ms)
    }
}

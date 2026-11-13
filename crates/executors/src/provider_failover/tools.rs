//! Task-scoped supervised actions, not blanket read-only eligibility. External or
//! command effects require exact checkpoint grants. Every mutation is write-ahead
//! fenced and a missing/failed native completion remains unknown across recovery.
use super::*;
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EffectGrant {
    pub effect_id: String,
    pub tool: String,
    pub input: serde_json::Value,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Actions {
    pub source_receipt: String,
    pub scope_key: String,
    pub qualification_version: String,
    pub local_writes: bool,
    pub effects: Vec<EffectGrant>,
}
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ToolUse {
    pub execution_id: String,
    pub tool_use_id: String,
    pub tool: String,
    pub input: serde_json::Value,
    pub effect_id: Option<String>,
    pub completed: bool,
    #[serde(default)]
    pub reconciled_outcome: Option<EffectOutcome>,
    pub source_receipt: Option<String>,
}
impl Actions {
    pub fn validate(&self, c: &Candidate, cp: &Checkpoint) -> io::Result<()> {
        if !present(&self.source_receipt)
            || self.scope_key != c.scope_key
            || self.qualification_version != c.qualification_version
            || self.effects.len() > 100
            || serde_json::to_vec(self)?.len() > 32_768
        {
            return Err(invalid("Actual task action qualification required"));
        }
        let mut ids = std::collections::BTreeSet::new();
        for grant in &self.effects {
            if !present(&grant.tool)
                || !ids.insert(&grant.effect_id)
                || !cp.effects.iter().any(|e| {
                    e.id == grant.effect_id
                        && e.outcome == EffectOutcome::NotStarted
                        && present(&e.receipt)
                })
            {
                return Err(invalid(
                    "External/command action needs exact verified-not-started checkpoint grant",
                ));
            }
        }
        Ok(())
    }
    pub fn allows(&self, cp: &Checkpoint, tool: &str, input: &serde_json::Value) -> bool {
        if matches!(
            tool,
            "Task" | "Agent" | "AskUserQuestion" | "ExitPlanMode" | "EnterPlanMode"
        ) {
            return false;
        }
        if claude::read_tool(tool) {
            return true;
        }
        if self.local_writes && matches!(tool, "Write" | "Edit") {
            let Some(path) = input.get("file_path").and_then(serde_json::Value::as_str) else {
                return false;
            };
            let path = Path::new(path);
            // Check existing ancestors so symlink/../escape aliases cannot acquire
            // write authority. Nonexistent nested files are allowed within the root.
            let Ok(root) = fs::canonicalize(&cp.workspace_path) else {
                return false;
            };
            if !path.is_absolute()
                || path
                    .components()
                    .any(|p| matches!(p, std::path::Component::ParentDir))
            {
                return false;
            }
            let mut ancestor = path;
            while !ancestor.exists() {
                let Some(parent) = ancestor.parent() else {
                    return false;
                };
                ancestor = parent;
            }
            return fs::canonicalize(ancestor).is_ok_and(|p| p.starts_with(root));
        }
        self.effects
            .iter()
            .any(|g| g.tool == tool && g.input == *input)
    }
}
/// Independent terminal reconciliation, never inferred from a preservation hash.
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ReconciledTool {
    pub execution_id: String,
    pub tool_use_id: String,
    pub tool: String,
    pub input: serde_json::Value,
    pub outcome: EffectOutcome,
    pub source_receipt: String,
}
impl Controller {
    pub fn reconcile_tool(&mut self, id: &str, proof: ReconciledTool) -> io::Result<()> {
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        let t = match &w.phase {
            Phase::Running(t) | Phase::DispatchPending(t)
                if t.execution_id == proof.execution_id =>
            {
                t
            }
            _ => return Err(invalid("Tool reconciliation owner mismatch")),
        };
        if !self.ended_safely(&t.execution_id)
            || !present(&proof.source_receipt)
            || proof.outcome == EffectOutcome::Unknown
        {
            return Err(invalid(
                "Terminal independently reconciled outcome required",
            ));
        }
        let key = format!("{}:{}", proof.execution_id, proof.tool_use_id);
        let old = self
            .state
            .tool_uses
            .get(&key)
            .ok_or_else(|| invalid("Unclaimed tool cannot manufacture successful admission"))?;
        if old.tool != proof.tool || old.input != proof.input {
            return Err(invalid("Immutable tool reconciliation mismatch"));
        }
        if old.completed {
            return if old.source_receipt.as_deref() == Some(proof.source_receipt.as_str())
                && old.reconciled_outcome.as_ref() == Some(&proof.outcome)
            {
                Ok(())
            } else {
                Err(invalid("Conflicting immutable tool outcome"))
            };
        }
        let mut next = self.state.clone();
        let tool = next.tool_uses.get_mut(&key).unwrap();
        tool.completed = true;
        tool.reconciled_outcome = Some(proof.outcome.clone());
        tool.source_receipt = Some(proof.source_receipt.clone());
        if let Some(effect) = &tool.effect_id {
            let e = next
                .works
                .get_mut(id)
                .unwrap()
                .effects
                .get_mut(effect)
                .ok_or_else(|| invalid("Missing effect"))?;
            e.outcome = proof.outcome;
            e.receipt = proof.source_receipt;
        }
        self.commit(next)
    }
    pub fn authorize_actions(&mut self, id: &str, actions: Actions) -> io::Result<()> {
        let w = self.work(id).ok_or_else(|| invalid("Unknown work"))?;
        let Phase::DispatchPending(t) = &w.phase else {
            return Err(invalid("Actions require exact pending owner"));
        };
        actions.validate(&t.candidate, &t.checkpoint)?;
        if let Some(old) = self.state.actions.get(&t.execution_id) {
            return if old == &actions {
                Ok(())
            } else {
                Err(invalid("Immutable task action scope changed"))
            };
        }
        let mut next = self.state.clone();
        next.actions.insert(t.execution_id.clone(), actions);
        self.commit(next)
    }
    pub(super) fn action_allowed(
        &self,
        id: &str,
        execution: &str,
        tool: &str,
        input: &serde_json::Value,
    ) -> bool {
        let Some(w) = self.work(id) else {
            return false;
        };
        let t = match &w.phase {
            Phase::DispatchPending(t) | Phase::Running(t) if t.execution_id == execution => t,
            _ => return false,
        };
        self.state.actions.get(execution).map_or_else(
            || claude::read_tool(tool),
            |a| a.allows(&t.checkpoint, tool, input),
        )
    }
    /// Called only AFTER actual approval but BEFORE returning Allow to native CLI.
    pub(super) fn claim_tool(
        &mut self,
        id: &str,
        execution: &str,
        tool_id: &str,
        tool: &str,
        input: &serde_json::Value,
    ) -> io::Result<()> {
        if !present(tool_id)
            || tool_id.len() > 200
            || !self.action_allowed(id, execution, tool, input)
            || serde_json::to_vec(input)?.len() > 65_536
        {
            return Err(invalid("Tool/action outside bounded authorized scope"));
        }
        if claude::read_tool(tool) {
            return Ok(());
        }
        let key = format!("{execution}:{tool_id}");
        if self.state.tool_uses.contains_key(&key) {
            return Err(invalid("Tool already claimed; reconcile, do not replay"));
        }
        let effect_id = self
            .state
            .actions
            .get(execution)
            .and_then(|a| {
                a.effects
                    .iter()
                    .find(|g| g.tool == tool && g.input == *input)
            })
            .map(|g| g.effect_id.clone());
        if let Some(e) = &effect_id
            && !self
                .work(id)
                .and_then(|w| w.effects.get(e))
                .is_some_and(|e| e.outcome == EffectOutcome::NotStarted)
        {
            return Err(invalid(
                "Effect completed/uncertain; cannot replay under a new tool ID",
            ));
        }
        let mut next = self.state.clone();
        if let Some(e) = &effect_id {
            let effect = next.works.get_mut(id).unwrap().effects.get_mut(e).unwrap();
            effect.outcome = EffectOutcome::Unknown;
            effect.receipt.clear();
        }
        next.tool_uses.insert(
            key,
            ToolUse {
                execution_id: execution.into(),
                tool_use_id: tool_id.into(),
                tool: tool.into(),
                input: input.clone(),
                effect_id,
                completed: false,
                reconciled_outcome: None,
                source_receipt: None,
            },
        );
        self.commit(next)
    }
    pub(super) fn complete_tool(
        &mut self,
        id: &str,
        execution: &str,
        tool_id: &str,
        tool: &str,
        input: &serde_json::Value,
    ) -> io::Result<()> {
        if claude::read_tool(tool) {
            return Ok(());
        }
        let key = format!("{execution}:{tool_id}");
        let claim = self
            .state
            .tool_uses
            .get(&key)
            .ok_or_else(|| invalid("Unclaimed native completion"))?;
        if claim.tool != tool || claim.input != *input {
            return Err(invalid("Native completion changed tool/input"));
        }
        if claim.completed {
            return if claim.reconciled_outcome == Some(EffectOutcome::Completed) {
                Ok(())
            } else {
                Err(invalid(
                    "Native completion contradicts independently reconciled not-started outcome",
                ))
            };
        }
        let receipt = format!("native-post-tool:{execution}:{tool_id}");
        let mut next = self.state.clone();
        let claim = next.tool_uses.get_mut(&key).unwrap();
        claim.completed = true;
        claim.reconciled_outcome = Some(EffectOutcome::Completed);
        claim.source_receipt = Some(receipt.clone());
        if let Some(e) = &claim.effect_id {
            let effect = next
                .works
                .get_mut(id)
                .ok_or_else(|| invalid("Unknown work"))?
                .effects
                .get_mut(e)
                .ok_or_else(|| invalid("Missing effect"))?;
            effect.outcome = EffectOutcome::Completed;
            effect.receipt = receipt;
        }
        self.commit(next)
    }
}

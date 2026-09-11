//! VK progress guard around Codex's native, persisted goal engine.
//! Codex owns objectives, scheduling, usage accounting and goal status. This file
//! stores only supporting evidence and circuit breakers, outside all repositories.
use std::{collections::BTreeMap, io, path::PathBuf};

use codex_app_server_protocol::DynamicToolSpec;
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

pub const TOOL: &str = "vk_goal_checkpoint";
pub const INSTRUCTIONS: &str = include_str!("goal_instructions.md");

#[derive(Debug, Clone, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct NativeGoal {
    pub thread_id: String,
    pub objective: String,
    pub status: String,
    pub created_at: i64,
}

#[derive(Debug, Clone, Default, Deserialize, Serialize)]
pub struct Progress {
    pub objective: String,
    pub created_at: i64,
    pub requirements: BTreeMap<String, String>,
    pub completed: BTreeMap<String, String>,
    pub turns: u32,
    pub stagnant_turns: u32,
    pub last_completed_count: usize,
    pub last_turn: Option<String>,
    pub pause_reason: Option<String>,
}

impl Progress {
    pub fn checkpoint(&mut self, args: Value) -> Result<Value, String> {
        #[derive(Deserialize)]
        #[serde(deny_unknown_fields)]
        struct Checkpoint {
            requirements: BTreeMap<String, String>,
            completed: BTreeMap<String, String>,
            disposition: String,
            reason: String,
        }
        let request: Checkpoint = serde_json::from_value(args).map_err(|e| e.to_string())?;
        if !matches!(request.disposition.as_str(), "continue" | "needs_input") {
            return Err("disposition must be continue or needs_input".into());
        }
        if request.disposition == "needs_input" && request.reason.trim().is_empty() {
            return Err("Explain the substantive reason user involvement is needed".into());
        }
        if request.requirements.len() > 100 || request.completed.len() > 100 {
            return Err("Use at most 100 material requirements".into());
        }
        for (id, text) in request.requirements.iter().chain(request.completed.iter()) {
            if id.trim().is_empty() || id.len() > 100 || text.trim().is_empty() || text.len() > 4000
            {
                return Err(
                    "IDs must be 1–100 bytes and descriptions/evidence 1–4000 bytes".into(),
                );
            }
        }
        if !self.requirements.is_empty()
            && !request.requirements.is_empty()
            && request.requirements != self.requirements
        {
            return Err(
                "The checklist is fixed. Read it using empty maps; do not redefine scope".into(),
            );
        }
        let requirements = if self.requirements.is_empty() {
            &request.requirements
        } else {
            &self.requirements
        };
        if request
            .completed
            .keys()
            .any(|id| !requirements.contains_key(id))
        {
            return Err("Completion must reference an existing requirement ID".into());
        }
        if self.requirements.is_empty() {
            self.requirements = request.requirements;
        }
        // Completed evidence is monotonic: repeatedly rewriting it is not progress.
        for (id, evidence) in request.completed {
            self.completed.entry(id).or_insert(evidence);
        }
        if request.disposition == "needs_input" {
            self.pause_reason = Some(request.reason.chars().take(4000).collect());
        }
        Ok(json!({
            "progress": self,
            "guidance": if self.stagnant_turns >= 3 {
                "Reassess the FULL objective. Stop revisiting completed work. Choose a different action closing a remaining requirement; request user input if none exists."
            } else { "Close remaining requirements with evidence; stop at sufficient completion." }
        }))
    }

    pub fn finish_turn(&mut self, turn_id: &str) -> Option<String> {
        if self.last_turn.as_deref() == Some(turn_id) {
            return self.pause_reason.clone();
        }
        self.last_turn = Some(turn_id.to_string());
        self.turns += 1;
        if self.completed.len() > self.last_completed_count {
            self.stagnant_turns = 0;
        } else {
            self.stagnant_turns += 1;
        }
        self.last_completed_count = self.completed.len();
        if self.pause_reason.is_none() {
            self.pause_reason = if self.stagnant_turns >= 6 {
                Some("Six goal turns closed no requirement. Reassess the remaining objective before resuming.".into())
            } else if self.turns >= 50 {
                Some(
                    "Fifty goal turns reached the run limit. Review progress before resuming."
                        .into(),
                )
            } else {
                None
            };
        }
        self.pause_reason.clone()
    }

    pub fn resume(&mut self) {
        self.turns = 0;
        self.stagnant_turns = 0;
        self.pause_reason = None;
        self.last_completed_count = self.completed.len();
    }

    pub fn all_complete(&self) -> bool {
        !self.requirements.is_empty() && self.requirements.len() == self.completed.len()
    }
}

pub fn tool_spec() -> DynamicToolSpec {
    DynamicToolSpec {
        name: TOOL.into(),
        description: "Read or update the durable VK checklist for an active native goal. Use empty maps to read. Define requirements once, then report completed IDs with validation evidence. needs_input pauses autonomy. Does not create or complete goals.".into(),
        defer_loading: false,
        input_schema: json!({
            "type": "object", "additionalProperties": false,
            "properties": {
                "requirements": {"type":"object", "additionalProperties":{"type":"string"}},
                "completed": {"type":"object", "additionalProperties":{"type":"string"}},
                "disposition": {"type":"string", "enum":["continue", "needs_input"]},
                "reason": {"type":"string"}
            },
            "required":["requirements", "completed", "disposition", "reason"]
        }),
    }
}

pub fn checkpoint_from_message(text: &str) -> Option<Value> {
    let body = text.trim().strip_suffix("</vk_goal_checkpoint>")?;
    let (_, json) = body.rsplit_once("<vk_goal_checkpoint>")?;
    if json.len() > 450_000 {
        return None;
    }
    serde_json::from_str(json).ok()
}

pub async fn describe(value: &Value) -> io::Result<String> {
    let Some(value) = value.get("goal").filter(|v| !v.is_null()) else {
        return Ok("No goal is set. Use /goal followed by the requested outcome.".into());
    };
    let goal: NativeGoal = serde_json::from_value(value.clone())?;
    let progress = load(&goal).await?;
    let mut message = format!(
        "**Goal:** {}\n\n**Status:** {}\n\n**Requirements verified:** {} of {}",
        goal.objective,
        goal.status,
        progress.completed.len(),
        progress.requirements.len()
    );
    if let Some(tokens) = value.get("tokensUsed").and_then(Value::as_u64) {
        message.push_str(&format!("\n\n**Tokens used:** {tokens}"));
        if let Some(budget) = value.get("tokenBudget").and_then(Value::as_u64) {
            message.push_str(&format!(" of {budget}"));
        }
    }
    if let Some(reason) = progress.pause_reason {
        message.push_str(&format!("\n\n{reason}"));
    }
    for (id, requirement) in &progress.requirements {
        message.push_str(&format!(
            "\n- [{}] {requirement}",
            if progress.completed.contains_key(id) {
                "x"
            } else {
                " "
            }
        ));
    }
    Ok(message)
}

pub fn progress_path(thread_id: &str) -> io::Result<PathBuf> {
    // Thread IDs are untrusted protocol input, never filesystem paths.
    if thread_id.is_empty()
        || thread_id.len() > 100
        || !thread_id
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || c == b'-' || c == b'_')
    {
        return Err(io::Error::other("Invalid goal thread ID"));
    }
    super::codex_home()
        .map(|p| p.join("vk-goal-progress").join(format!("{thread_id}.json")))
        .ok_or_else(|| io::Error::other("Codex home unavailable for durable goal progress"))
}

pub async fn load(goal: &NativeGoal) -> io::Result<Progress> {
    let path = progress_path(&goal.thread_id)?;
    match tokio::fs::read(path).await {
        Ok(bytes) => {
            let progress: Progress = serde_json::from_slice(&bytes)?;
            if progress.objective == goal.objective && progress.created_at == goal.created_at {
                return Ok(progress);
            }
        }
        Err(err) if err.kind() == io::ErrorKind::NotFound => {}
        Err(err) => return Err(err),
    }
    Ok(Progress {
        objective: goal.objective.clone(),
        created_at: goal.created_at,
        ..Default::default()
    })
}

pub async fn save(thread_id: &str, progress: &Progress) -> io::Result<()> {
    let path = progress_path(thread_id)?;
    tokio::fs::create_dir_all(path.parent().expect("progress parent")).await?;
    let temporary = path.with_extension(format!("{}.tmp", uuid::Uuid::new_v4()));
    tokio::fs::write(&temporary, serde_json::to_vec(progress)?).await?;
    tokio::fs::rename(temporary, path).await
}

#[cfg(test)]
mod tests {
    use super::*;

    fn report(requirements: Value, completed: Value) -> Value {
        json!({"requirements": requirements, "completed": completed, "disposition":"continue", "reason":""})
    }

    #[test]
    fn substantial_eight_stage_objective_moves_between_requirements() {
        let mut p = Progress::default();
        let requirements: BTreeMap<_, _> = (0..8)
            .map(|n| (format!("gap-{n}"), format!("Verify material outcome {n}")))
            .collect();
        p.checkpoint(report(json!(requirements), json!({})))
            .unwrap();
        for stage in 0..8 {
            // Investigation and implementation may span turns before verification.
            assert!(p.finish_turn(&format!("investigate-{stage}")).is_none());
            assert!(p.finish_turn(&format!("implement-{stage}")).is_none());
            p.checkpoint(report(
                json!({}),
                json!({format!("gap-{stage}"): format!("Integration evidence for {stage}")}),
            ))
            .unwrap();
            assert!(p.finish_turn(&format!("verify-{stage}")).is_none());
            assert_eq!(p.stagnant_turns, 0);
            // Simulate executor restart/compaction; evidence survives serialization.
            p = serde_json::from_str(&serde_json::to_string(&p).unwrap()).unwrap();
        }
        assert!(p.all_complete());
        assert_eq!(p.turns, 24);
    }

    #[test]
    fn refinement_and_reworded_evidence_do_not_extend_autonomy() {
        let mut p = Progress::default();
        p.checkpoint(report(
            json!({"ui":"UI parity", "api":"API parity"}),
            json!({"ui":"UI checked"}),
        ))
        .unwrap();
        assert!(p.finish_turn("first").is_none());
        for n in 1..=6 {
            p.checkpoint(report(
                json!({}),
                json!({"ui": format!("Polished and retested {n}")}),
            ))
            .unwrap();
            assert_eq!(p.finish_turn(&format!("polish-{n}")).is_some(), n == 6);
        }
        assert_eq!(p.completed.len(), 1);
        assert!(!p.all_complete());
        let turns = p.turns;
        p.finish_turn("polish-6");
        assert_eq!(p.turns, turns, "duplicate notifications must be idempotent");
    }

    #[test]
    fn refusal_to_checkpoint_also_stops() {
        let mut p = Progress::default();
        for n in 0..6 {
            p.finish_turn(&n.to_string());
        }
        assert!(p.pause_reason.is_some());
    }

    #[test]
    fn scope_cannot_shrink_or_rotate_and_invalid_updates_are_atomic() {
        let mut p = Progress::default();
        p.checkpoint(report(json!({"one":"First", "two":"Second"}), json!({})))
            .unwrap();
        assert!(
            p.checkpoint(report(json!({"one":"First"}), json!({"one":"done"})))
                .is_err()
        );
        assert!(
            p.checkpoint(report(json!({}), json!({"fake":"done"})))
                .is_err()
        );
        assert!(p.completed.is_empty());
        assert_eq!(p.requirements.len(), 2);
        assert!(!p.all_complete());
    }

    #[test]
    fn hard_limit_bounds_even_claimed_progress_and_resume_keeps_evidence() {
        let mut p = Progress::default();
        let requirements: BTreeMap<_, _> = (0..60)
            .map(|n| (n.to_string(), "Material gap".into()))
            .collect();
        p.requirements = requirements;
        for n in 0..50 {
            p.completed.insert(n.to_string(), "evidence".into());
            assert_eq!(p.finish_turn(&n.to_string()).is_some(), n == 49);
        }
        p.resume();
        assert_eq!(p.completed.len(), 50);
        assert_eq!(p.turns, 0);
        assert!(p.pause_reason.is_none());
    }

    #[test]
    fn substantive_user_input_pauses_without_claiming_completion() {
        let mut p = Progress::default();
        p.checkpoint(json!({"requirements":{},"completed":{},"disposition":"needs_input","reason":"Choose the required API compatibility policy"})).unwrap();
        assert!(p.pause_reason.is_some());
        assert!(!p.all_complete());
    }

    #[test]
    fn thread_ids_cannot_escape_instance_state_directory() {
        for id in ["", "../secret", "a/b", "a\\b", "/tmp/x"] {
            assert!(progress_path(id).is_err());
        }
        assert!(progress_path("test-thread_123").is_ok());
    }
}

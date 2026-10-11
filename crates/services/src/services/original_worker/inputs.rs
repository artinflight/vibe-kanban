//! Native input freshness, independent of the mutable VK execution action.
//! Release capture pins the complete input prefix, including rollback events.
use std::{collections::HashMap, io, path::PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::Value;
use sqlx::{
    Connection,
    sqlite::{SqliteConnectOptions, SqliteConnection},
};

use super::{digest, invalid};

#[derive(Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct InputSeal {
    pub coverage_id: uuid::Uuid,
    pub backend_sequence: i64,
    pub rollout: PathBuf,
    pub records: usize,
    pub prefix_digest: String,
}

struct Input {
    kind: String,
    payload: Value,
    text: Option<String>,
}

fn inputs(bytes: &[u8]) -> io::Result<Vec<Input>> {
    let mut result = Vec::new();
    for line in bytes.split(|b| *b == b'\n').filter(|l| !l.is_empty()) {
        let entry: Value = serde_json::from_slice(line)
            .map_err(|_| invalid("Native history incomplete or invalid"))?;
        let kind = entry["type"]
            .as_str()
            .ok_or_else(|| invalid("Unknown native history envelope"))?;
        let p = &entry["payload"];
        let event = p["type"].as_str().unwrap_or("");
        if kind == "response_item" && event == "message" && p["role"] == "user" {
            // Adopted historical inputs may contain images. Preserve their entire
            // payload in the prefix seal; only newly dispatched plain text can
            // match a backend-owned continuation receipt.
            let text = p["content"].as_array().and_then(|content| {
                content.iter().try_fold(String::new(), |mut text, item| {
                    if item["type"] != "input_text" {
                        return None;
                    }
                    text.push_str(item["text"].as_str()?);
                    Some(text)
                })
            });
            result.push(Input {
                kind: "response".into(),
                payload: p.clone(),
                text,
            });
        } else if kind == "event_msg" && event == "user_message" {
            result.push(Input {
                kind: "event".into(),
                payload: p.clone(),
                text: Some(
                    p["message"]
                        .as_str()
                        .ok_or_else(|| invalid("Unknown native steering text"))?
                        .into(),
                ),
            });
        } else if kind == "event_msg"
            && ["rollback", "rolled_back", "reset", "steer", "drop", "input"]
                .iter()
                .any(|s| event.contains(s))
        {
            result.push(Input {
                kind: "amendment".into(),
                payload: p.clone(),
                text: None,
            });
        } else if !matches!(
            kind,
            "session_meta" | "turn_context" | "response_item" | "event_msg" | "compacted"
        ) {
            return Err(invalid("Unknown native history record"));
        } else if kind == "compacted" {
            result.push(Input {
                kind: "amendment".into(),
                payload: p.clone(),
                text: None,
            });
        }
    }
    Ok(result)
}

pub fn verify(bytes: &[u8], seal: &InputSeal, authorized: &[String]) -> io::Result<()> {
    let records = inputs(bytes)?;
    if records.len() < seal.records {
        return Err(invalid("Native input history was reset"));
    }
    let prefix: Vec<&Value> = records[..seal.records].iter().map(|r| &r.payload).collect();
    if digest(&serde_json::to_vec(&prefix)?) != seal.prefix_digest {
        return Err(invalid("Native input prefix changed"));
    }
    let mut seen = HashMap::<(String, String), usize>::new();
    for r in &records[seal.records..] {
        let text = r
            .text
            .as_ref()
            .ok_or_else(|| invalid("Native input history amended"))?;
        let hash = digest(text.as_bytes());
        let allowed = authorized.iter().filter(|d| **d == hash).count();
        let count = seen.entry((r.kind.clone(), hash)).or_default();
        *count += 1;
        if *count > allowed {
            return Err(invalid("Unaccounted native user or steering input"));
        }
    }
    Ok(())
}

pub async fn read(thread: &str, seal: &InputSeal) -> io::Result<Vec<u8>> {
    let home = executors::executors::codex::codex_home()
        .ok_or_else(|| invalid("Native home unavailable"))?;
    let mut db = SqliteConnection::connect_with(
        &SqliteConnectOptions::new()
            .filename(home.join("state_5.sqlite"))
            .read_only(true)
            .create_if_missing(false),
    )
    .await
    .map_err(|_| invalid("Native input index unavailable"))?;
    let path: String = sqlx::query_scalar("SELECT rollout_path FROM threads WHERE id=?")
        .bind(thread)
        .fetch_one(&mut db)
        .await
        .map_err(|_| invalid("Native rollout binding unavailable"))?;
    let path = PathBuf::from(path).canonicalize()?;
    if path != seal.rollout || !path.starts_with(home.canonicalize()?) {
        return Err(invalid("Native rollout binding changed"));
    }
    if tokio::fs::metadata(&path).await?.len() > 128 * 1024 * 1024 {
        return Err(invalid("Native history exceeds verification bound"));
    }
    tokio::fs::read(path).await
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn wire(v: Value) -> Vec<u8> {
        serde_json::to_vec(&v).unwrap()
    }
    fn seal() -> InputSeal {
        InputSeal {
            coverage_id: uuid::Uuid::new_v4(),
            backend_sequence: 0,
            rollout: "/synthetic/native.jsonl".into(),
            records: 0,
            prefix_digest: digest(b"[]"),
        }
    }
    #[test]
    fn unchanged_goal_does_not_hide_steering_or_dropped_reset_history() {
        for payload in [
            json!({"type":"user_message","message":"Synthetic amendment"}),
            json!({"type":"thread_rolled_back","num_turns":1}),
            json!({"type":"input_dropped","id":"synthetic"}),
        ] {
            assert!(
                verify(
                    &wire(json!({"type":"event_msg","payload":payload})),
                    &seal(),
                    &[]
                )
                .is_err()
            );
        }
        assert!(verify(b"{\"type\":", &seal(), &[]).is_err());
    }
    #[test]
    fn only_exact_activated_input_and_one_record_per_native_kind_are_admitted() {
        let event = wire(
            json!({"type":"event_msg","payload":{"type":"user_message","message":"Synthetic fixed continuation"}}),
        );
        let response = wire(
            json!({"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"Synthetic fixed continuation"}]}}),
        );
        let allowed = [digest(b"Synthetic fixed continuation")];
        let mut both = event.clone();
        both.push(b'\n');
        both.extend_from_slice(&response);
        verify(&both, &seal(), &allowed).unwrap();
        both.push(b'\n');
        both.extend_from_slice(&event);
        assert!(verify(&both, &seal(), &allowed).is_err());
        assert!(verify(&response, &seal(), &[digest(b"Altered synthetic prompt")]).is_err());
    }
    #[test]
    fn pinned_prefix_cannot_be_truncated_or_replaced() {
        let p = json!({"type":"user_message","message":"Synthetic adopted input"});
        let seal = InputSeal {
            records: 1,
            prefix_digest: digest(&wire(json!([p.clone()]))),
            ..seal()
        };
        verify(&wire(json!({"type":"event_msg","payload":p})), &seal, &[]).unwrap();
        assert!(verify(b"", &seal, &[]).is_err());
        assert!(verify(&wire(json!({"type":"event_msg","payload":{"type":"user_message","message":"Changed synthetic input"}})),&seal,&[]).is_err());
    }
}

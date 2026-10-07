//! Read only retained historical copies using the exact repaired normalizer.
use std::{collections::BTreeMap, path::Path, time::Duration};

use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use utils::{execution_logs::read_execution_log_strict, log_msg::LogMsg};

#[tokio::main]
async fn main() {
    let root =
        Path::new("/mnt/vk-storage/vk-combined-release-20261007/connector-review/historical");
    let audit: Value =
        serde_json::from_slice(&std::fs::read(root.join("historical-report-audit.json")).unwrap())
            .unwrap();
    let mut all_passed = true;
    for row in audit["reports"].as_array().unwrap() {
        let path = Path::new(row["private_copy"].as_str().unwrap());
        assert_eq!(path.parent(), Some(root));
        let (bytes, messages) = read_execution_log_strict(path, 32 * 1024 * 1024)
            .await
            .unwrap();
        let hash = format!("{:x}", Sha256::digest(&bytes));
        assert_eq!(hash, row["source_sha256"]);
        let stdout: String = messages
            .iter()
            .filter_map(|m| match m {
                LogMsg::Stdout(s) => Some(s.as_str()),
                _ => None,
            })
            .collect();
        let rejected: Vec<_> = stdout.lines().enumerate().filter_map(|(index, line)| {
            executors::executors::codex::normalize_logs::validate_review_line(line).err().map(|e| {
                let event: Value = serde_json::from_str(line).unwrap_or(Value::Null);
                json!({"line": index + 1, "method": event["method"],
                    "params_keys": event["params"].as_object().map(|v| v.keys().collect::<Vec<_>>()),
                    "item_type": event["params"]["item"]["type"],
                    "item_keys": event["params"]["item"].as_object().map(|v| v.keys().collect::<Vec<_>>()),
                    "error": e.to_string(), "line_sha256": format!("{:x}", Sha256::digest(line.as_bytes()))})
            })
        }).collect();
        let normalized = tokio::time::timeout(
            Duration::from_secs(10),
            services::services::report_review::normalize_review_log(messages, root),
        )
        .await;
        let mut entries = BTreeMap::<usize, Value>::new();
        let mut error = None;
        let mut finished = false;
        match normalized {
            Ok(Ok(messages)) => {
                for msg in messages {
                    match msg {
                        LogMsg::JsonPatch(patch) => {
                            // Audit reducer handles complete entry replacements only;
                            // it does not silently accept unknown patch shapes.
                            for op in serde_json::to_value(patch).unwrap().as_array().unwrap() {
                                let parts: Vec<_> =
                                    op["path"].as_str().unwrap().split('/').collect();
                                assert_eq!(parts.len(), 3);
                                assert_eq!(parts[1], "entries");
                                let index = parts[2].parse().unwrap();
                                match op["op"].as_str().unwrap() {
                                    "add" | "replace" => {
                                        entries.insert(index, op["value"].clone());
                                    }
                                    "remove" => {
                                        entries.remove(&index);
                                    }
                                    _ => panic!("Unsupported historical audit patch"),
                                }
                            }
                        }
                        LogMsg::Finished => finished = true,
                        _ => panic!("Unexpected normalized review message"),
                    }
                }
            }
            Ok(Err(e)) => error = Some(e.to_string()),
            Err(_) => error = Some("Strict normalization timed out".into()),
        }
        let final_reply = entries.iter().rev().find(|(_, e)| {
            e["type"] == "NORMALIZED_ENTRY"
                && e["content"]["entry_type"]["type"] == "assistant_message"
        });
        let observed = final_reply.map(|(index, e)| json!({"index": index,
            "sha256": format!("{:x}", Sha256::digest(e["content"]["content"].as_str().unwrap().as_bytes()))}));
        let matches = observed.as_ref().is_some_and(|reply| {
            reply["index"] == row["identity"]["message_index"]
                && reply["sha256"] == row["identity"]["reply_sha256"]
        });
        let content_matches = observed.as_ref().is_some_and(|reply| {
            reply["sha256"] == row["identity"]["reply_sha256"]
        });
        // Historical index reconciliation and writer closure are separate gates;
        // this audit proves parsing/content compatibility, never permission to mark.
        all_passed &= finished && content_matches && rejected.is_empty();
        println!(
            "{}",
            json!({"execution": row["identity"]["execution_id"], "raw_sha256": hash,
            "raw_bytes": bytes.len(), "strict_replay_finished": finished, "error": error,
            "rejected_native_events": rejected,
            "observed_final_reply": observed, "receipt_identity_matches": matches,
            "reply_content_matches": content_matches, "historical_receipt_eligible": false,
            "historical_writer_fence_certified": false, "production_changed": false})
        );
    }
    if !all_passed {
        std::process::exit(1);
    }
}

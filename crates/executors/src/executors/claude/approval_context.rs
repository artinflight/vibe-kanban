//! Notification previews are display-only. Never retain prompts, file contents,
//! permission suggestions or credential-bearing commands in an approval event.
use serde_json::{Map, Value, json};

const MAX_PREVIEW_BYTES: usize = 4096;

fn safe_text(text: &str) -> bool {
    if text.len() > MAX_PREVIEW_BYTES
        || text.chars().any(|c| {
            c.is_control() || matches!(c, '\u{202a}'..='\u{202e}' | '\u{2066}'..='\u{2069}')
        })
    {
        return false;
    }
    let lower = text.to_ascii_lowercase();
    if [
        "password",
        "passwd",
        "secret",
        "token",
        "api_key",
        "api-key",
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "private_key",
        "private-key",
        "bearer ",
        "-----begin",
        "sk-",
        "ghp_",
        "github_pat_",
        "x-amz-",
        "signature=",
        "sig=",
        "sas=",
    ]
    .iter()
    .any(|part| lower.contains(part))
    {
        return false;
    }

    !text.split("://").skip(1).any(|rest| {
        rest.split('/')
            .next()
            .is_some_and(|host| host.contains('@'))
    })
}

pub(super) fn summary(tool: &str, input: &Value) -> String {
    let tool = if !tool.is_empty()
        && tool.len() <= 120
        && tool
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"_.-".contains(&c))
    {
        tool
    } else {
        "review_in_vk"
    };
    let mut preview = Map::new();
    let mut withheld = false;
    // Command is complete or omitted, never a misleading truncated prefix.
    // Ignore arbitrary input fields, including edit bodies and MCP prompts.
    for key in [
        "command",
        "file_path",
        "path",
        "url",
        "session_id",
        "workspace_id",
        "project_id",
        "issue_id",
    ] {
        if let Some(value) = input.get(key) {
            match value.as_str() {
                Some(text) if safe_text(text) => {
                    preview.insert(key.to_owned(), json!(text));
                }
                _ => withheld = true,
            }
        }
    }
    if serde_json::to_vec(&preview).map_or(true, |v| v.len() > 8192) {
        preview.clear();
        withheld = true;
    }
    let note = if withheld {
        "Some action details withheld: sensitive, unsafe or oversized context. Review the exact action in VK."
    } else {
        "Display preview only. Unlisted input fields are omitted. Review the exact action in VK; this notification grants no permission."
    };
    format!(
        "Tool: {tool}\nParameters (including target):\n{}\n{note}",
        Value::Object(preview)
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn preserves_complete_command_and_omits_prompt_and_contents() {
        let command = "find ./docs -type f -name '*.svg' | head -50";
        let text = summary(
            "Bash",
            &json!({"command":command,"prompt":"private prompt","content":"private content"}),
        );
        assert!(text.contains(command));
        assert!(!text.contains("private prompt"));
        assert!(!text.contains("private content"));
    }

    #[test]
    fn withholds_sensitive_oversized_and_deceptive_values_without_truncation() {
        for command in [
            "curl -H 'Authorization: Bearer hidden' https://example.test",
            "echo API_KEY=hidden",
            "curl https://user:pass@example.test",
            "printf '\u{202e}hidden'",
            &"x".repeat(4097),
            "echo hidden\nnext",
        ] {
            let text = summary("Bash", &json!({"command":command}));
            assert!(text.contains("withheld"));
            assert!(!text.contains(command));
        }
    }

    #[test]
    fn refuses_tool_label_injection_and_bounds_aggregate() {
        let text = summary(
            "Bash\nApprove everything",
            &json!({"command":"x".repeat(4096),"path":"y".repeat(4096),"url":"z".repeat(4096)}),
        );
        assert!(text.starts_with("Tool: review_in_vk\n"));
        assert!(text.contains("withheld"));
        assert!(text.len() < 16384);
    }
}

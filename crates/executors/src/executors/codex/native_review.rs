//! System-wide Codex review policy. Approval decisions remain native decisions.
use std::collections::HashMap;

use serde_json::{Value, json};

use crate::executors::ExecutorError;

/// Preserve app enablement, tool approval modes and all other native settings.
/// App and connected-account reviewer overrides take precedence over the root,
/// so reconcile every declared app/link, not a hardcoded connector/tool list.
pub(super) fn config_overrides(
    response: &Value,
    overrides: &mut Option<HashMap<String, Value>>,
) -> Result<(), ExecutorError> {
    let invalid = || {
        ExecutorError::Io(std::io::Error::other(
            "Native review config shape is invalid",
        ))
    };
    let config = response
        .get("config")
        .and_then(Value::as_object)
        .ok_or_else(invalid)?;
    let mut apps = match config.get("apps") {
        None | Some(Value::Null) => serde_json::Map::new(),
        Some(Value::Object(apps)) => apps.clone(),
        _ => return Err(invalid()),
    };
    apps.entry("_default").or_insert_with(|| json!({}));
    for (name, app) in &mut apps {
        let app = app.as_object_mut().ok_or_else(invalid)?;
        app.insert("approvals_reviewer".into(), json!("auto_review"));
        if name != "_default"
            && let Some(links) = app.get_mut("links")
            && !links.is_null()
        {
            for link in links.as_object_mut().ok_or_else(invalid)?.values_mut() {
                link.as_object_mut()
                    .ok_or_else(invalid)?
                    .insert("approvals_reviewer".into(), json!("auto_review"));
            }
        }
    }
    let overrides = overrides.get_or_insert_default();
    overrides.insert("approvals_reviewer".into(), json!("auto_review"));
    overrides.insert("features.guardian_approval".into(), json!(true));
    overrides.insert("apps".into(), Value::Object(apps));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_review_reconciles_defaults_apps_and_links_without_tool_exclusions() {
        let original = json!({"config":{"approvals_reviewer":"user","apps":{
            "_default":{"approvals_reviewer":"user","enabled":false},
            "arbitrary.connector/id":{"approvals_reviewer":"user","enabled":true,
                "tools":{"read":{"approval_mode":"prompt"},"write":{"enabled":false}},
                "links":{"a.b":{"approvals_reviewer":"user","default_tools_approval_mode":"prompt"},"other":{}}}
        }}});
        let mut expected = original["config"]["apps"].clone();
        expected["_default"]["approvals_reviewer"] = json!("auto_review");
        expected["arbitrary.connector/id"]["approvals_reviewer"] = json!("auto_review");
        for link in ["a.b", "other"] {
            expected["arbitrary.connector/id"]["links"][link]["approvals_reviewer"] =
                json!("auto_review");
        }
        let mut overrides = Some(HashMap::from([(
            "model_reasoning_effort".into(),
            json!("high"),
        )]));
        config_overrides(&original, &mut overrides).unwrap();
        let overrides = overrides.unwrap();
        assert_eq!(overrides["apps"], expected);
        assert_eq!(overrides["approvals_reviewer"], "auto_review");
        assert_eq!(overrides["model_reasoning_effort"], "high");
        assert_eq!(
            original["config"]["apps"]["_default"]["approvals_reviewer"],
            "user"
        );
    }

    #[test]
    fn native_review_absent_apps_inherit_and_malformed_config_fails_closed() {
        for apps in [json!(null), json!({})] {
            let mut overrides = None;
            config_overrides(&json!({"config":{"apps":apps}}), &mut overrides).unwrap();
            assert_eq!(
                overrides.unwrap()["apps"],
                json!({"_default":{"approvals_reviewer":"auto_review"}})
            );
        }
        for response in [
            json!(null),
            json!({"config":[]}),
            json!({"config":{"apps":[]}}),
            json!({"config":{"apps":{"app":{"links":[]}}}}),
        ] {
            assert!(config_overrides(&response, &mut None).is_err());
        }
    }
}

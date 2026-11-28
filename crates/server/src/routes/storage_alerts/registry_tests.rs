//! Source-only tests for the additive owner-file parser. Native CI must execute them.
use super::*;

fn owner(workspace: Uuid, session: Uuid) -> OwnerBinding {
    OwnerBinding {
        workspace_id: workspace,
        session_id: session,
        executor_config: serde_json::from_value(serde_json::json!({"executor": "CODEX"}))
            .expect("existing executor-config serde defaults"),
        max_validation_age_seconds: 60,
        delegation_journal_dir: None,
    }
}

#[test]
fn registry_selects_multiple_targets_and_keeps_legacy_file() {
    let a = owner(Uuid::new_v4(), Uuid::new_v4());
    let b = owner(Uuid::new_v4(), Uuid::new_v4());
    let bytes = serde_json::to_vec(&serde_json::json!({"version":1,"owners":[a,b]})).unwrap();
    assert_eq!(
        select_binding(&bytes, a.workspace_id, a.session_id)
            .unwrap()
            .session_id,
        a.session_id
    );
    assert_eq!(
        select_binding(&bytes, b.workspace_id, b.session_id)
            .unwrap()
            .session_id,
        b.session_id
    );
    assert!(select_binding(&bytes, a.workspace_id, b.session_id).is_err());
    let legacy = serde_json::to_vec(&a).unwrap();
    assert!(select_binding(&legacy, a.workspace_id, a.session_id).is_ok());
}

#[test]
fn registry_reload_removal_duplicate_version_and_size_fail_closed() {
    let a = owner(Uuid::new_v4(), Uuid::new_v4());
    let one = serde_json::to_vec(&serde_json::json!({"version":1,"owners":[a]})).unwrap();
    assert!(select_binding(&one, a.workspace_id, a.session_id).is_ok());
    let removed = serde_json::to_vec(&serde_json::json!({"version":1,"owners":[]})).unwrap();
    assert!(select_binding(&removed, a.workspace_id, a.session_id).is_err());
    let duplicate = serde_json::to_vec(&serde_json::json!({"version":1,"owners":[a,a]})).unwrap();
    assert!(select_binding(&duplicate, a.workspace_id, a.session_id).is_err());
    let unsupported = serde_json::to_vec(&serde_json::json!({"version":2,"owners":[a]})).unwrap();
    assert!(select_binding(&unsupported, a.workspace_id, a.session_id).is_err());
    assert!(select_binding(&vec![b' '; 65537], a.workspace_id, a.session_id).is_err());
}

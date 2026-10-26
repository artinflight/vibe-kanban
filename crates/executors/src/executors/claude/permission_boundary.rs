//! Authorize ordinary workspace edits before native explicit deny/ask evaluation.
use std::{
    io::ErrorKind,
    path::{Component, Path, PathBuf},
};

use serde_json::Value;

pub(super) const QUALIFIED_VERSION: &str = "2.1.77";
pub(super) const CALLBACK_ID: &str = "workspace_edit_boundary";

// Resolve existing ancestors too: a new file underneath a symlink must not get
// the lexical workspace grant. Missing/ambiguous/unreadable paths require review.
fn resolve_target(path: &Path) -> Option<PathBuf> {
    let mut ancestor = path.to_path_buf();
    let mut tail = Vec::new();
    loop {
        match ancestor.canonicalize() {
            Ok(mut resolved) => {
                for part in tail.into_iter().rev() {
                    resolved.push(part);
                }
                return Some(resolved);
            }
            Err(error) if error.kind() == ErrorKind::NotFound => {
                tail.push(ancestor.file_name()?.to_owned());
                if !ancestor.pop() {
                    return None;
                }
            }
            Err(_) => return None,
        }
    }
}

pub(super) fn allows_workspace_edit(root: Option<&Path>, event: &Value) -> bool {
    let Some(root) = root.filter(|root| root.is_absolute() && root.parent().is_some()) else {
        return false;
    };
    // Native Plan may write its own planning files, but never auto-authorize
    // source edits here. Unknown/new modes also fall back to native evaluation.
    if event.get("permission_mode").and_then(Value::as_str) != Some("default") {
        return false;
    }
    let key = match event.get("tool_name").and_then(Value::as_str) {
        Some("Write" | "Edit" | "MultiEdit") => "file_path",
        Some("NotebookEdit") => "notebook_path",
        _ => return false,
    };
    let Some(path) = event
        .get("tool_input")
        .and_then(|v| v.get(key))
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
    else {
        return false;
    };
    let path = Path::new(path);
    let requested = if path.is_absolute() {
        path.to_path_buf()
    } else {
        root.join(path)
    };
    let Some(resolved) = resolve_target(&requested) else {
        return false;
    };
    if resolved.components().any(|part| matches!(part, Component::Normal(name) if
        [".git", ".claude", ".codex", ".agents", ".aws"].iter().any(|blocked| name.as_encoded_bytes().eq_ignore_ascii_case(blocked.as_bytes())))) {
        return false;
    }
    // No native allow rule is installed. External, symlink-escaped and ambiguous
    // paths fall back to native Default rules and request-bound owner approval.
    resolved.starts_with(root)
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    fn event(path: &Path) -> Value {
        json!({"permission_mode":"default","tool_name":"Write","tool_input":{"file_path":path}})
    }

    #[test]
    fn native_edit_boundary_keeps_workspace_grant_scoped_and_metadata_interactive() {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().join("workspace");
        std::fs::create_dir(&root).unwrap();
        let root = root.canonicalize().unwrap();
        assert!(allows_workspace_edit(
            Some(&root),
            &event(&root.join("new/deep/file.txt"))
        ));
        for name in [".git", ".claude", ".codex", ".agents", ".aws"] {
            assert!(!allows_workspace_edit(
                Some(&root),
                &event(&root.join(name).join("config"))
            ));
        }
        assert!(!allows_workspace_edit(
            Some(&root),
            &event(&root.join("../outside.txt"))
        ));
        assert!(
            !allows_workspace_edit(Some(&root), &event(&temp.path().join("outside.txt"))),
            "Explicit direct outside rules still belong to native evaluation"
        );
        assert!(!allows_workspace_edit(None, &event(&root.join("file.txt"))));
        assert!(
            !allows_workspace_edit(root.ancestors().last(), &event(&root.join("file.txt"))),
            "A filesystem root must never become an automatic global grant"
        );
        for mode in ["plan", "acceptEdits", "bypassPermissions", "unknown"] {
            let mut value = event(&root.join("file.txt"));
            value["permission_mode"] = json!(mode);
            assert!(!allows_workspace_edit(Some(&root), &value));
        }
        for invalid in [
            json!({}),
            json!({"tool_name":"Write","tool_input":{"file_path":""}}),
            json!({"tool_name":"Write","tool_input":{"file_path":2}}),
        ] {
            assert!(!allows_workspace_edit(Some(&root), &invalid));
        }
    }

    #[cfg(unix)]
    #[test]
    fn native_edit_boundary_resolves_new_files_under_symlink_directories() {
        let temp = tempfile::tempdir().unwrap();
        let root = temp.path().join("workspace");
        let outside = temp.path().join("outside");
        std::fs::create_dir(&root).unwrap();
        std::fs::create_dir(&outside).unwrap();
        std::os::unix::fs::symlink(&outside, root.join("linked")).unwrap();
        let root = root.canonicalize().unwrap();
        assert!(!allows_workspace_edit(
            Some(&root),
            &event(&root.join("linked/new/file.txt"))
        ));
        assert!(!outside.join("new").exists());
    }
}

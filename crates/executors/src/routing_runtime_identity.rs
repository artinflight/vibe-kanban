//! The terminal label in Codex's user agent is not runtime identity.
//! Keep version, platform, architecture and client identity exact.
fn without_terminal(runtime: &str) -> Option<&str> {
    let runtime = runtime.strip_suffix(" (vk_routing_probe; 1)")?;
    let (identity, terminal) = runtime.rsplit_once(") ")?;
    if !identity.starts_with("vk_routing_probe/")
        || terminal.is_empty()
        || !terminal
            .bytes()
            .all(|c| c.is_ascii_alphanumeric() || b"-_.".contains(&c))
    {
        return None;
    }
    Some(identity)
}

pub(crate) fn matches(saved: Option<&str>, current: Option<&str>) -> bool {
    let (Some(saved), Some(current)) = (saved, current) else {
        return false;
    };
    if saved.is_empty() || current.is_empty() {
        return false;
    }
    saved == current
        || matches!(
            (without_terminal(saved), without_terminal(current)),
            (Some(saved), Some(current)) if saved == current
        )
}

#[cfg(test)]
mod tests {
    use super::matches;

    const SAVED: &str =
        "vk_routing_probe/0.159.2 (Ubuntu 24.4.0; x86_64) dumb (vk_routing_probe; 1)";

    #[test]
    fn terminal_changes_do_not_invalidate_execution_evidence() {
        for terminal in ["dumb", "unknown", "xterm-256color"] {
            let current = SAVED.replace(") dumb (", &format!(") {terminal} ("));
            assert!(matches(Some(SAVED), Some(&current)));
        }
    }

    #[test]
    fn runtime_platform_architecture_and_client_changes_still_fail_closed() {
        for current in [
            SAVED.replace("0.159.2", "0.160.0"),
            SAVED.replace("Ubuntu 24.4.0", "Ubuntu 26.4.0"),
            SAVED.replace("x86_64", "aarch64"),
            SAVED.replace("; 1)", "; 2)"),
            SAVED.replace(") dumb (", ") malformed terminal ("),
        ] {
            assert!(!matches(Some(SAVED), Some(&current)), "{current}");
        }
    }

    #[test]
    fn missing_or_unknown_identity_shapes_are_not_normalized() {
        assert!(!matches(None, None));
        assert!(!matches(Some(""), Some("")));
        assert!(matches(Some("native-v1"), Some("native-v1")));
        assert!(!matches(Some("native-v1"), Some("native-v2")));
        assert!(!matches(Some(SAVED), None));
    }
}

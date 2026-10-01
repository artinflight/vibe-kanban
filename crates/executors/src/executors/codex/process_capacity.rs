//! Conservative fallback inventory, not an inference-activity monitor.
//! Count native app-server engines once, plus launchers still waiting for an engine.
//! Never treat command text inside shells/diagnostics as a running Codex command.
use std::{collections::HashMap, path::Path};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Kind {
    Engine,
    Launcher,
}

fn invocation(args: &[String]) -> Option<Kind> {
    let name = |arg: &str| {
        Path::new(arg)
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_owned()
    };
    let first = name(args.first()?);
    let (kind, mut at) = match first.as_str() {
        "codex" => (Kind::Engine, 1),
        "node" | "nodejs"
            if matches!(
                name(args.get(1)?).as_str(),
                "codex" | "codex.js" | "codex.mjs"
            ) =>
        {
            (Kind::Launcher, 2)
        }
        _ => return None,
    };
    // Global options may precede the real subcommand. Do not scan arbitrary argument text.
    while let Some(arg) = args.get(at) {
        match arg.as_str() {
            "-c" | "--config" | "--enable" | "--disable" | "-p" | "--profile" => {
                args.get(at + 1)?;
                at += 2;
            }
            _ if ["--config=", "--enable=", "--disable=", "--profile="]
                .iter()
                .any(|p| arg.starts_with(p)) =>
            {
                at += 1
            }
            "app-server" => return Some(kind),
            _ => return None,
        }
    }
    None
}

fn count(rows: &HashMap<u32, (u32, Kind)>) -> usize {
    rows.iter()
        .filter(|(pid, (_, kind))| {
            // Engines always count, including two distinct engines under one launcher.
            // A launcher counts only while it has no matched child. This collapses
            // node -> node -> native chains without collapsing independently started engines.
            *kind == Kind::Engine || !rows.values().any(|(parent, _)| parent == *pid)
        })
        .count()
}

#[cfg(target_os = "linux")]
pub(super) fn app_server_count() -> usize {
    let entries = match std::fs::read_dir("/proc") {
        Ok(entries) => entries,
        Err(error) => {
            tracing::warn!(%error,"Cannot inspect Codex capacity; deny admission rather than assume zero");
            return usize::MAX;
        }
    };
    let mut rows = HashMap::new();
    for entry in entries.flatten() {
        let Some(pid) = entry
            .file_name()
            .to_str()
            .and_then(|s| s.parse::<u32>().ok())
        else {
            continue;
        };
        let Ok(cmdline) = std::fs::read(entry.path().join("cmdline")) else {
            continue;
        };
        let args: Vec<_> = cmdline
            .split(|c| *c == 0)
            .filter(|a| !a.is_empty())
            .map(|a| String::from_utf8_lossy(a).into_owned())
            .collect();
        let Some(kind) = invocation(&args) else {
            continue;
        };
        let Ok(stat) = std::fs::read_to_string(entry.path().join("stat")) else {
            continue;
        };
        let Some((_, suffix)) = stat.rsplit_once(')') else {
            continue;
        };
        let mut fields = suffix.split_whitespace();
        if matches!(fields.next(), None | Some("Z" | "X")) {
            continue;
        }
        let Some(parent) = fields.next().and_then(|s| s.parse().ok()) else {
            continue;
        };
        rows.insert(pid, (parent, kind));
    }
    let total = count(&rows);
    tracing::debug!(
        matched_processes = rows.len(),
        app_servers = total,
        "Codex fallback capacity inventory"
    );
    total
}

#[cfg(test)]
mod tests {
    use super::*;
    fn args(items: &[&str]) -> Vec<String> {
        items.iter().map(|s| s.to_string()).collect()
    }
    #[test]
    fn capacity_matches_commands_not_mentions_or_other_subcommands() {
        assert_eq!(
            invocation(&args(&["/usr/bin/codex", "app-server"])),
            Some(Kind::Engine)
        );
        assert_eq!(
            invocation(&args(&["node", "/runtime/codex.mjs", "app-server"])),
            Some(Kind::Launcher)
        );
        assert_eq!(
            invocation(&args(&[
                "node",
                "/bin/codex",
                "-c",
                "features.goals=true",
                "app-server"
            ])),
            Some(Kind::Launcher)
        );
        for a in [
            vec!["bash", "-lc", "codex app-server"],
            vec!["python3", "-c", "count codex app-server"],
            vec!["codex", "exec", "app-server"],
            vec!["node", "other.js", "app-server"],
        ] {
            assert_eq!(invocation(&args(&a)), None);
        }
    }
    #[test]
    fn capacity_collapses_launcher_chains_and_counts_startup_and_sibling_engines() {
        let mut rows = HashMap::from([
            (1, (0, Kind::Launcher)),
            (2, (1, Kind::Launcher)),
            (3, (2, Kind::Engine)),
        ]);
        assert_eq!(count(&rows), 1);
        rows.insert(4, (0, Kind::Launcher));
        assert_eq!(count(&rows), 2); // starting engine
        rows.insert(5, (4, Kind::Engine));
        rows.insert(6, (4, Kind::Engine));
        assert_eq!(count(&rows), 3);
        rows.insert(7, (3, Kind::Engine));
        assert_eq!(count(&rows), 4); // separate child engine
    }
    #[test]
    fn capacity_counts_orphan_engine_conservatively() {
        assert_eq!(count(&HashMap::from([(1, (999, Kind::Engine))])), 1);
    }
}

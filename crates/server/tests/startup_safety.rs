//! Exercise the real binary only inside private filesystem/PID/network namespaces.
#[cfg(target_os = "linux")]
#[test]
fn server_invocations_and_runtime_identity_are_isolated() {
    let repository = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap()
        .parent()
        .unwrap();
    let output = std::process::Command::new("python3")
        .arg("-B")
        .arg(repository.join("scripts/testing/startup-recovery-safety/server_sandbox.py"))
        .arg("--binary")
        .arg(env!("CARGO_BIN_EXE_server"))
        .output()
        .expect("Python and bubblewrap are required for isolated startup tests");
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
}

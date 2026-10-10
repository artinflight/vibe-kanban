// Shared guard for compiled HTTP and real-writer acceptance. No production fallback.
pub fn assert_fixture_root() {
    // Debug asset storage is scoped to the compiled checkout. Never fall back
    // to production's home/XDG storage, including release-mode tests.
    const {
        assert!(
            cfg!(debug_assertions),
            "Review fixtures require checkout-local debug storage"
        );
    }
    let compiled_root = std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .unwrap();
    assert_eq!(
        utils::assets::asset_dir().canonicalize().unwrap(),
        compiled_root.join("dev_assets").canonicalize().unwrap()
    );
    if let Ok(requested_root) = std::env::var("VK_REVIEW_ACCEPTANCE_ROOT") {
        assert_eq!(
            std::path::PathBuf::from(requested_root)
                .canonicalize()
                .unwrap(),
            compiled_root
        );
    }
    // CI runners use their ephemeral checkout. This MCP host must use its SSD.
    if std::path::Path::new("/home/mcp/code/vibe-dot-connector").exists() {
        assert!(compiled_root.starts_with("/mnt/vk-storage/"));
    }
}

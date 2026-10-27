//! Current in-repo adapter, real router/SQLite/launch/approval bridge; executor I/O synthetic.
use axum::routing::get;
use serde_json::json;

use super::*;

pub(super) async fn exercise() {
    let (dir, d, first, _) = fixture().await;
    let second_dir = dir.path().join("second");
    std::fs::create_dir(&second_dir).unwrap();
    let (second, _) = seed_owner(&second_dir, &d, "synthetic-secondary-thread").await;
    let owner_file = PathBuf::from(std::env::var_os("VK_STORAGE_ALERT_OWNER_FILE").unwrap());
    std::fs::write(&owner_file, serde_json::to_vec(&first).unwrap()).unwrap();
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let address = listener.local_addr().unwrap();
    let app: Router = Router::new()
        .nest("/api", super::super::router().with_state(d.clone()))
        .merge(
            Router::new()
                .route(
                    "/__fixture",
                    get(super::native_adapter::state).post(super::native_adapter::control),
                )
                .with_state((d.clone(), first.clone())),
        )
        .merge(
            Router::new()
                .route(
                    "/__fixture/secondary",
                    get(super::native_adapter::state).post(super::native_adapter::control),
                )
                .with_state((d.clone(), second.clone())),
        );
    let stop = CancellationToken::new();
    let shutdown = stop.clone();
    let server = tokio::spawn(async move {
        axum::serve(listener, app)
            .with_graceful_shutdown(shutdown.cancelled_owned())
            .await
            .unwrap();
    });
    let descriptor = dir.path().join("modular-descriptor.json");
    std::fs::write(&descriptor,serde_json::to_vec(&json!({
        "fixture_protocol":"modular-native-fixture-v1", "base_url":format!("http://{address}/api"),
        "control_url":format!("http://{address}/__fixture"),"state_root":dir.path(),
        "owner_file":owner_file,"owners":[first,second],"server_epoch":Uuid::new_v4()
    })).unwrap()).unwrap();
    let driver = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("../../scripts/watcher-events/modular_native_integration.py");
    let output = tokio::time::timeout(
        std::time::Duration::from_secs(90),
        tokio::process::Command::new("python3")
            .arg("-B")
            .arg(driver)
            .arg(&descriptor)
            .kill_on_drop(true)
            .output(),
    )
    .await
    .unwrap()
    .unwrap();
    stop.cancel();
    tokio::time::timeout(std::time::Duration::from_secs(5), server)
        .await
        .unwrap()
        .unwrap();
    assert!(
        output.status.success(),
        "{}\n{}",
        String::from_utf8_lossy(&output.stdout),
        String::from_utf8_lossy(&output.stderr)
    );
    let evidence: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(evidence["status"], "passed");
    assert_eq!(evidence["backend_listener_count"], 1);
    assert_eq!(evidence["owner_targets"], 2);
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 3);
    println!("MODULAR_NATIVE_EVIDENCE {evidence}");
}

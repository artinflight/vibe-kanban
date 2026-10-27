//! Current in-repo adapter, real router/SQLite/launch/approval bridge; executor I/O synthetic.
use axum::routing::get;
use serde_json::json;

use super::*;

pub(super) fn process_start_ticks() -> String {
    std::fs::read_to_string("/proc/self/stat")
        .unwrap()
        .rsplit_once(')')
        .unwrap()
        .1
        .split_whitespace()
        .nth(19)
        .unwrap()
        .to_owned()
}

fn process_identity() -> serde_json::Value {
    use std::io::Read;

    use sha2::{Digest, Sha256};
    let mut file = std::fs::File::open(std::env::current_exe().unwrap()).unwrap();
    let mut digest = Sha256::new();
    let mut bytes = [0; 65536];
    loop {
        let count = file.read(&mut bytes).unwrap();
        if count == 0 {
            break;
        }
        digest.update(&bytes[..count]);
    }
    json!({"pid":std::process::id(),"start_ticks":process_start_ticks(),"binary_sha256":format!("{:x}",digest.finalize())})
}

pub(super) async fn exercise() {
    let (dir, d, first, _) = fixture().await;
    let second_dir = dir.path().join("second");
    std::fs::create_dir(&second_dir).unwrap();
    let (mut second, _) = seed_owner(&second_dir, &d, "synthetic-secondary-thread").await;
    second.max_validation_age_seconds = 300;
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
    let identity = process_identity();
    let descriptor = dir.path().join("modular-descriptor.json");
    std::fs::write(&descriptor,serde_json::to_vec(&json!({
        "fixture_protocol":"modular-native-fixture-v1", "base_url":format!("http://{address}/api"),
        "control_url":format!("http://{address}/__fixture"),"state_root":dir.path(),
        "owner_file":owner_file,"owners":[first,second],"server_identity":identity
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
    assert_eq!(
        identity,
        process_identity(),
        "same native backend PID/start/executable throughout configuration updates"
    );
    assert_eq!(evidence["server_identity"], identity);
    assert_eq!(evidence["backend_listener_count"], 1);
    assert_eq!(evidence["owner_targets"], 2);
    assert_eq!(d.container.launches.load(Ordering::SeqCst), 5);
    println!("MODULAR_NATIVE_EVIDENCE {evidence}");
}

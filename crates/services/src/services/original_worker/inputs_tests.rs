use serde_json::json;

use super::*;

#[tokio::test]
async fn large_sealed_input_prefix_is_streamed_through_the_native_index() {
    let home = tempfile::tempdir().unwrap();
    let (_db, mut seal) = native_fixture(home.path()).await;
    let payload = json!({"type":"message","role":"user","content":[{"type":"input_text","text":"x".repeat(128 * 1024)}]});
    let payload_bytes = serde_json::to_vec(&payload).unwrap();
    let mut row = serde_json::to_vec(&json!({"type":"response_item","payload":payload})).unwrap();
    row.push(b'\n');
    let mut file = io::BufWriter::new(File::create(&seal.rollout).unwrap());
    let mut reference = Sha256::new();
    reference.update(b"[");
    for i in 0..1280 {
        if i != 0 {
            reference.update(b",");
        }
        reference.update(&payload_bytes);
        file.write_all(&row).unwrap();
    }
    file.flush().unwrap();
    reference.update(b"]");
    seal.records = 1280;
    seal.prefix_digest = format!("{:x}", reference.finalize());
    assert!(std::fs::metadata(&seal.rollout).unwrap().len() > 160 * 1024 * 1024);
    verify_in_home(home.path(), "synthetic", &seal, &[])
        .await
        .unwrap();
}

fn sealed(payloads: &[Value]) -> InputSeal {
    InputSeal {
        coverage_id: uuid::Uuid::new_v4(),
        backend_sequence: 0,
        rollout: PathBuf::new(),
        records: payloads.len(),
        prefix_digest: digest(&serde_json::to_vec(payloads).unwrap()),
    }
}

#[test]
fn prefix_encoding_matches_original_including_images_unicode_and_amendments() {
    let rows = [
        json!({"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_image","image_url":"data:synthetic"},{"type":"input_text","text":"café\n\"quoted\""}]}}),
        json!({"type":"event_msg","payload":{"type":"thread_rolled_back","num_turns":2}}),
        json!({"type":"compacted","payload":{"message":"synthetic","replacement_history":[]}}),
        json!({"type":"world_state","payload":{"full":true,"state":{"permissions":{"instructions":"synthetic"}}}}),
    ];
    let payloads: Vec<_> = rows.iter().map(|r| r["payload"].clone()).collect();
    let seal = sealed(&payloads);
    let mut bytes = Vec::new();
    for row in &rows {
        serde_json::to_writer(&mut bytes, row).unwrap();
        bytes.extend_from_slice(b"\n\n");
    }
    verify(&bytes, &seal, &[]).unwrap();
    let mut changed = rows[3].clone();
    changed["payload"]["state"]["permissions"]["instructions"] = json!("changed");
    bytes.extend_from_slice(&serde_json::to_vec(&changed).unwrap());
    assert!(verify(&bytes, &seal, &[]).is_err());
    assert!(
        verify(
            &serde_json::to_vec(&rows[0]).unwrap(),
            &sealed(&[]),
            &[digest("café\n\"quoted\"".as_bytes())]
        )
        .is_err()
    );
}

#[test]
fn malformed_ignored_output_unknown_envelopes_and_overlong_records_fail_closed() {
    for row in [
        b"{\"type\":\"response_item\",\"payload\":{\"type\":\"message\"}".as_slice(),
        b"{\"type\":\"unknown_future_record\",\"payload\":{}}",
        b"{\"type\":\"token_usage_record\",\"payload\":NaN}",
        b"{}",
    ] {
        assert!(verify(row, &sealed(&[]), &[]).is_err());
    }
    // A streamed source, not an oversized test allocation; take() must stop it.
    let reader = BufReader::new(io::repeat(b' ').take(MAX_RECORD_BYTES + 1024));
    assert!(
        verify_stream(reader, &sealed(&[]), &[])
            .unwrap_err()
            .to_string()
            .contains("bound")
    );
}

async fn native_fixture(home: &Path) -> (SqliteConnection, InputSeal) {
    let mut db = SqliteConnection::connect_with(
        &SqliteConnectOptions::new()
            .filename(home.join("state_5.sqlite"))
            .create_if_missing(true),
    )
    .await
    .unwrap();
    sqlx::query("CREATE TABLE threads(id TEXT PRIMARY KEY, rollout_path TEXT)")
        .execute(&mut db)
        .await
        .unwrap();
    let path = home.join("rollout.jsonl");
    std::fs::write(
        &path,
        b"{\"type\":\"event_msg\",\"payload\":{\"type\":\"task_complete\"}}\n",
    )
    .unwrap();
    sqlx::query("INSERT INTO threads VALUES ('synthetic',?)")
        .bind(path.to_str().unwrap())
        .execute(&mut db)
        .await
        .unwrap();
    let mut seal = sealed(&[]);
    seal.rollout = path.canonicalize().unwrap();
    (db, seal)
}

#[tokio::test]
async fn indexed_scan_detects_concurrent_append_truncate_rewrite_replace_and_rebinding() {
    for case in [
        "append",
        "truncate",
        "rewrite",
        "replace",
        "rebind",
        "index_replace",
    ] {
        let home = tempfile::tempdir().unwrap();
        let (mut db, seal) = native_fixture(home.path()).await;
        let original = std::fs::read(&seal.rollout).unwrap();
        let result = verify_after_scan(home.path(), "synthetic", &seal, &[], || async {
            match case {
                "append" => std::fs::OpenOptions::new()
                    .append(true)
                    .open(&seal.rollout)?
                    .write_all(b"\n")?,
                "truncate" => File::options()
                    .write(true)
                    .open(&seal.rollout)?
                    .set_len(0)?,
                "rewrite" => std::fs::write(&seal.rollout, &original)?,
                "replace" => {
                    let next = home.path().join("replacement");
                    std::fs::write(&next, &original)?;
                    std::fs::rename(next, &seal.rollout)?;
                }
                "rebind" => {
                    sqlx::query("UPDATE threads SET rollout_path=?")
                        .bind(home.path().join("other.jsonl").to_str().unwrap())
                        .execute(&mut db)
                        .await
                        .unwrap();
                }
                "index_replace" => {
                    std::fs::rename(
                        home.path().join("state_5.sqlite"),
                        home.path().join("old.sqlite"),
                    )?;
                    std::fs::write(home.path().join("state_5.sqlite"), b"replacement")?;
                }
                _ => unreachable!(),
            }
            Ok(())
        })
        .await;
        assert!(
            result.is_err(),
            "concurrent {case} must not verify a stale view"
        );
    }
}

#[tokio::test]
async fn native_index_is_read_only_home_bound_and_concurrent_readers_agree() {
    let home = tempfile::tempdir().unwrap();
    let (mut db, seal) = native_fixture(home.path()).await;
    let (a, b) = tokio::join!(
        verify_in_home(home.path(), "synthetic", &seal, &[]),
        verify_in_home(home.path(), "synthetic", &seal, &[])
    );
    a.unwrap();
    b.unwrap();
    assert!(
        verify_in_home(home.path(), "missing", &seal, &[])
            .await
            .is_err()
    );
    let outside = tempfile::NamedTempFile::new().unwrap();
    sqlx::query("UPDATE threads SET rollout_path=?")
        .bind(outside.path().to_str().unwrap())
        .execute(&mut db)
        .await
        .unwrap();
    let mut escaped = seal.clone();
    escaped.rollout = outside.path().canonicalize().unwrap();
    assert!(
        verify_in_home(home.path(), "synthetic", &escaped, &[])
            .await
            .is_err()
    );
    let missing_home = tempfile::tempdir().unwrap();
    assert!(
        verify_in_home(missing_home.path(), "synthetic", &seal, &[])
            .await
            .is_err()
    );
    assert!(!missing_home.path().join("state_5.sqlite").exists());
}

#[tokio::test]
#[ignore = "Explicit private read-only acceptance manifest required; no live grants or dispatch"]
async fn verify_private_history_read_only() {
    #[derive(Deserialize)]
    #[serde(deny_unknown_fields)]
    struct Request {
        home: PathBuf,
        thread: String,
        seal: InputSeal,
        authorized: Vec<String>,
    }
    let path =
        std::env::var_os("VK_HISTORY_ACCEPTANCE_REQUEST").expect("Private request path required");
    let bytes = std::fs::read(path).unwrap();
    assert!(bytes.len() < 128_000);
    let request: Request = serde_json::from_slice(&bytes).unwrap();
    let start = std::time::Instant::now();
    let result = verify_in_home(
        &request.home,
        &request.thread,
        &request.seal,
        &request.authorized,
    )
    .await;
    // Diagnostics deliberately contain no private paths, IDs, hashes or input.
    println!(
        "read_only_history_verification={} elapsed_ms={}",
        if result.is_ok() { "passed" } else { "refused" },
        start.elapsed().as_millis()
    );
    assert!(
        result.is_ok(),
        "Native freshness not proved: {}",
        result.unwrap_err()
    );
}

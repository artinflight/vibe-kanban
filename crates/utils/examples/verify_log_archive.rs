//! Qualify a packed tree with the same reader used by the backend.
use std::{fs, io::Read, path::PathBuf};

use serde_json::Value;
use sha2::{Digest, Sha256};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = PathBuf::from(std::env::args_os().nth(1).ok_or("Expected archive root")?);
    let receipt: Value = serde_json::from_slice(&fs::read(root.join("receipt.json"))?)?;
    let files = receipt["files"].as_array().ok_or("Missing file receipt")?;
    let mut total = 0u64;
    for entry in files {
        let relative = entry["path"].as_str().ok_or("Missing relative path")?;
        if !std::path::Path::new(relative)
            .components()
            .all(|c| matches!(c, std::path::Component::Normal(_)))
        {
            return Err("Invalid relative path".into());
        }
        let mut reader = utils::log_archive::open(&root.join(relative))?;
        let mut digest = Sha256::new();
        let mut count = 0u64;
        let mut buffer = [0u8; 65536];
        loop {
            let n = reader.read(&mut buffer)?;
            if n == 0 {
                break;
            }
            digest.update(&buffer[..n]);
            count += n as u64;
        }
        if Some(count) != entry["raw_bytes"].as_u64()
            || Some(format!("{:x}", digest.finalize()).as_str()) != entry["sha256"].as_str()
        {
            return Err("Reconstructed log does not match receipt".into());
        }
        total += count;
    }
    println!(
        "{}",
        serde_json::json!({"verified":true,"files":files.len(),"raw_bytes":total})
    );
    Ok(())
}

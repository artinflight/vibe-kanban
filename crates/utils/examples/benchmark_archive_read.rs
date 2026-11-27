//! Read-only full-EOF qualification. Prints hashes/timings, never log contents.
use std::{io::Read, path::PathBuf, time::Instant};

use sha2::{Digest, Sha256};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let paths: Vec<PathBuf> = std::env::args_os().skip(1).map(PathBuf::from).collect();
    if paths.is_empty() || paths.len() > 32 {
        return Err("Supply between one and 32 isolated archive paths".into());
    }
    let mut results = Vec::new();
    for path in paths {
        let start = Instant::now();
        let mut stream = utils::log_archive::open(&path)?;
        let mut hash = Sha256::new();
        let mut bytes = 0u64;
        let mut buffer = [0; 256 * 1024];
        loop {
            let count = stream.read(&mut buffer)?;
            if count == 0 {
                break;
            }
            hash.update(&buffer[..count]);
            bytes += count as u64;
        }
        results.push(serde_json::json!({
            "bytes": bytes, "sha256": format!("{:x}", hash.finalize()),
            "seconds": start.elapsed().as_secs_f64(), "full_eof_verified": true
        }));
    }
    println!("{}", serde_json::to_string(&results)?);
    Ok(())
}

//! Test-only child process using the actual production lock implementation.
#[path = "../../crates/utils/src/log_mutation.rs"]
mod log_mutation;
use std::{io::{Read, Write}, path::Path};
fn main() {
    let args: Vec<_> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("--build-info") {
        println!("{{\"executionLogMutationLockProtocol\":{}}}", log_mutation::PROTOCOL);
        return;
    }
    if args.len() != 3 || args[1] != "--hold" { std::process::exit(2); }
    let _guard = match log_mutation::LogMutationGuard::try_acquire(Path::new(&args[2])) {
        Ok(guard) => guard,
        Err(error) => { eprintln!("{error}"); std::process::exit(3); }
    };
    println!("LOCKED"); std::io::stdout().flush().unwrap();
    let mut byte = [0]; let _ = std::io::stdin().read(&mut byte);
}

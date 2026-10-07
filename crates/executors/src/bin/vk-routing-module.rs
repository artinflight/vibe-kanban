//! Stateless sandboxed classification worker. No repository or runtime access.
use std::io::{Read, Write};

fn main() {
    let result = (|| -> Result<(), String> {
        let args: Vec<_> = std::env::args().skip(1).collect();
        if args == ["--defaults"] {
            let value = serde_json::json!({"protocol":executors::routing_module::PROTOCOL,"models":serde_json::from_str::<serde_json::Value>(include_str!("../routing_models.json")).map_err(|_| "Invalid defaults")?,
                "instructions":executors::routing_semantic::DEFAULT_INSTRUCTIONS});
            println!("{value}");
            return Ok(());
        }
        if args.len() == 2 && args[0] == "--verify-release" {
            let value = executors::routing_module::verify_release(std::path::Path::new(&args[1]))?;
            println!("{value}");
            return Ok(());
        }
        if !args.is_empty() {
            return Err("Unsupported command".into());
        }
        let mut input = Vec::new();
        std::io::stdin()
            .take(65537)
            .read_to_end(&mut input)
            .map_err(|_| "Input failed")?;
        if input.len() > 65536 {
            return Err("Oversized request".into());
        }
        let request = serde_json::from_slice(&input).map_err(|_| "Invalid request")?;
        let reply = executors::routing_module::evaluate(request)?;
        let bytes = serde_json::to_vec(&reply).map_err(|_| "Output failed")?;
        std::io::stdout()
            .write_all(&bytes)
            .map_err(|_| "Output failed")?;
        Ok(())
    })();
    if result.is_err() {
        std::process::exit(1);
    }
}

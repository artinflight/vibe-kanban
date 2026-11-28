#[tokio::main]
async fn main() {
    if let Err(error) = server::run_native_final_repair(std::env::args().skip(1).collect()).await {
        eprintln!("Recovery refused: {error}");
        std::process::exit(1);
    }
}

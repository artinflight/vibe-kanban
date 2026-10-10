pub mod error;
pub mod middleware;
pub mod relay_pairing;
pub mod routes;
pub mod runtime;
pub mod startup;

// #[cfg(feature = "cloud")]
// type DeploymentImpl = vibe_kanban_cloud::deployment::CloudDeployment;
// #[cfg(not(feature = "cloud"))]
pub type DeploymentImpl = local_deployment::LocalDeployment;

/// Bounded same-UID incident recovery; never constructs a deployment or migrates.
pub async fn run_native_final_repair(args: Vec<String>) -> Result<(), String> {
    #[cfg(target_os = "linux")]
    {
        routes::execution_processes::historical_response::local_repair::run(args).await
    }
    #[cfg(not(target_os = "linux"))]
    {
        let _ = args;
        Err("Same-UID incident recovery requires the existing Linux service host".into())
    }
}

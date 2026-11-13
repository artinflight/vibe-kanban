use axum::{extract::State, response::IntoResponse};
use deployment::Deployment;

use crate::{DeploymentImpl, middleware::signed_ws::SignedWsUpgrade};

pub(super) async fn ssh_session_ws(
    State(deployment): State<DeploymentImpl>,
    ws: SignedWsUpgrade,
) -> impl IntoResponse {
    let writer_lease = match services::services::admission::interactive_writer() {
        Ok(lease) => lease,
        Err(error) => return (axum::http::StatusCode::CONFLICT, error).into_response(),
    };
    let ssh_config = deployment.ssh_config().clone();
    let relay_signing = deployment.relay_signing().clone();

    ws.on_upgrade(move |socket| async move {
        let _writer_lease = writer_lease;
        let stream = ws_bridge::axum_ws_stream_io(socket);
        if let Err(error) = embedded_ssh::run_ssh_session(stream, ssh_config, relay_signing).await {
            tracing::warn!(?error, "SSH session failed");
        }
    })
    .into_response()
}

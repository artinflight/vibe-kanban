use axum::{extract::Request, middleware::Next, response::Response};

/// Git UI mutations and owner launches share the checkpoint's idle boundary.
/// Request bodies stay owned by the normal handler; no queue or prompt is replaced.
pub async fn checkpoint_admission(request: Request, next: Next) -> Response {
    if request.method() == axum::http::Method::GET || request.method() == axum::http::Method::HEAD {
        return next.run(request).await;
    }
    services::services::admission::run(next.run(request)).await
}

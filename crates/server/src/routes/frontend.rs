use std::{
    env,
    path::{Component, Path, PathBuf},
};

use axum::{
    body::Body,
    http::HeaderValue,
    response::{IntoResponse, Response},
};
use reqwest::{StatusCode, header};
use rust_embed::RustEmbed;
use tokio::fs;

#[derive(RustEmbed)]
#[folder = "../../packages/local-web/dist"]
struct Assets;

const FRONTEND_DIST_DIR_ENV: &str = "VK_FRONTEND_DIST_DIR";
const HTML_CACHE_CONTROL: &str = "no-cache, no-store, must-revalidate";
const ASSET_CACHE_CONTROL: &str = "public, max-age=31536000, immutable";

pub(super) async fn serve_frontend(uri: axum::extract::Path<String>) -> impl IntoResponse {
    let path = uri.trim_start_matches('/');
    serve_file(path).await
}

pub(super) async fn serve_frontend_root() -> impl IntoResponse {
    serve_file("index.html").await
}

async fn serve_file(path: &str) -> impl IntoResponse + use<> {
    let path = normalize_frontend_path(path).unwrap_or_else(|| "index.html".to_string());

    if let Some(root) = frontend_dist_dir() {
        if let Some(response) = serve_disk_file(&root, &path).await {
            return response;
        }

        // For SPA routing, serve the override index.html for unknown routes.
        if path != "index.html"
            && let Some(response) = serve_disk_file(&root, "index.html").await
        {
            return response;
        }
    }

    serve_embedded_file(&path)
}

fn serve_embedded_file(path: &str) -> Response {
    let file = Assets::get(path);

    match file {
        Some(content) => ok_response(path, Body::from(content.data.into_owned())),
        None => {
            // For SPA routing, serve index.html for unknown routes
            if let Some(index) = Assets::get("index.html") {
                ok_response("index.html", Body::from(index.data.into_owned()))
            } else {
                Response::builder()
                    .status(StatusCode::NOT_FOUND)
                    .body(Body::from("404 Not Found"))
                    .unwrap()
            }
        }
    }
}

async fn serve_disk_file(root: &Path, path: &str) -> Option<Response> {
    let file_path = root.join(path);
    let content = match fs::read(&file_path).await {
        Ok(content) => content,
        Err(error) => {
            if error.kind() != std::io::ErrorKind::NotFound {
                tracing::warn!(
                    path = %file_path.display(),
                    error = %error,
                    "Failed to read frontend override asset"
                );
            }
            return None;
        }
    };

    Some(ok_response(path, Body::from(content)))
}

fn ok_response(path: &str, body: Body) -> Response {
    let mime = mime_guess::from_path(path).first_or_octet_stream();

    Response::builder()
        .status(StatusCode::OK)
        .header(
            header::CONTENT_TYPE,
            HeaderValue::from_str(mime.as_ref()).unwrap(),
        )
        .header(header::CACHE_CONTROL, cache_control_for_path(path))
        .body(body)
        .unwrap()
}

fn cache_control_for_path(path: &str) -> &'static str {
    if path.starts_with("assets/") {
        ASSET_CACHE_CONTROL
    } else {
        HTML_CACHE_CONTROL
    }
}

fn frontend_dist_dir() -> Option<PathBuf> {
    env::var_os(FRONTEND_DIST_DIR_ENV)
        .filter(|value| !value.is_empty())
        .map(PathBuf::from)
}

fn normalize_frontend_path(path: &str) -> Option<String> {
    let mut parts = Vec::new();

    for component in Path::new(path).components() {
        match component {
            Component::Normal(part) => parts.push(part.to_str()?.to_string()),
            Component::CurDir => {}
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => return None,
        }
    }

    if parts.is_empty() {
        Some("index.html".to_string())
    } else {
        Some(parts.join("/"))
    }
}

#[cfg(test)]
mod tests {
    use super::{ASSET_CACHE_CONTROL, HTML_CACHE_CONTROL};

    #[test]
    fn normalize_frontend_path_rejects_traversal() {
        assert_eq!(
            super::normalize_frontend_path("assets/index.js").as_deref(),
            Some("assets/index.js")
        );
        assert_eq!(
            super::normalize_frontend_path("").as_deref(),
            Some("index.html")
        );
        assert_eq!(super::normalize_frontend_path("../secret"), None);
        assert_eq!(super::normalize_frontend_path("assets/../../secret"), None);
        assert_eq!(super::normalize_frontend_path("/absolute"), None);
    }

    #[test]
    fn cache_control_keeps_index_refreshable() {
        assert_eq!(
            super::cache_control_for_path("index.html"),
            HTML_CACHE_CONTROL
        );
        assert_eq!(
            super::cache_control_for_path("site.webmanifest"),
            HTML_CACHE_CONTROL
        );
        assert_eq!(
            super::cache_control_for_path("assets/index-abc123.js"),
            ASSET_CACHE_CONTROL
        );
    }
}

use std::{
    env,
    path::{Component, PathBuf},
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

async fn serve_file(path: &str) -> Response {
    if let Some(response) = serve_external_file(path).await {
        return response;
    }

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

async fn serve_external_file(path: &str) -> Option<Response> {
    let frontend_dir = env::var_os("VK_FRONTEND_DIST_DIR").map(PathBuf::from)?;
    let safe_path = sanitize_asset_path(path)?;
    let file_path = frontend_dir.join(&safe_path);

    if let Ok(content) = fs::read(&file_path).await {
        return Some(file_response(path, content));
    }

    if path.starts_with("assets/") {
        return Some(
            Response::builder()
                .status(StatusCode::NOT_FOUND)
                .body(Body::from("404 Not Found"))
                .unwrap(),
        );
    }

    let index_path = frontend_dir.join("index.html");
    fs::read(index_path)
        .await
        .ok()
        .map(|content| file_response("index.html", content))
}

fn sanitize_asset_path(path: &str) -> Option<PathBuf> {
    let mut safe_path = PathBuf::new();

    for component in PathBuf::from(path).components() {
        match component {
            Component::Normal(part) => safe_path.push(part),
            Component::CurDir => {}
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => return None,
        }
    }

    Some(safe_path)
}

fn file_response(path: &str, content: Vec<u8>) -> Response {
    let mime = mime_guess::from_path(path).first_or_octet_stream();

    Response::builder()
        .status(StatusCode::OK)
        .header(
            header::CONTENT_TYPE,
            HeaderValue::from_str(mime.as_ref()).unwrap(),
        )
        .body(Body::from(content))
        .unwrap()
}

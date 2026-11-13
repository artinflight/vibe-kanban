//! AG-only raw diagnostic boundary. Never buffer or persist untrusted stderr.
//! Deliberately withhold every runtime diagnostic, including informational URLs:
//! arbitrary tokens/codes cannot be identified safely by a URL regex alone.
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};

const LABEL: &[u8] =
    b"[Antigravity ACP runtime diagnostic withheld; authorization data is not stored]\n";

pub(super) async fn drain<R, W>(mut input: R, mut output: W)
where
    R: AsyncRead + Unpin,
    W: AsyncWrite + Unpin,
{
    let mut buffer = [0_u8; 4096];
    let mut reported = false;
    loop {
        match input.read(&mut buffer).await {
            Ok(0) => break,
            Ok(_) => {
                if !reported {
                    // Even an output failure must not stop draining the child.
                    let _ = output.write_all(LABEL).await;
                    reported = true;
                }
            }
            Err(_) => {
                if !reported {
                    let _ = output.write_all(LABEL).await;
                }
                break;
            }
        }
    }
    let _ = output.shutdown().await;
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn split_oauth_code_and_tail_never_enter_capture_pipe() {
        let (mut source, raw) = tokio::io::duplex(128);
        let (filtered, mut capture) = tokio::io::duplex(256);
        let task = tokio::spawn(drain(raw, filtered));
        for chunk in [
            b"https://accounts.goo".as_slice(),
            b"gle.com/o/oauth2/v2/auth?state=SYNTHETIC_SECRET\n",
            b"code: SYNTHETIC_CODE no-newline-tail",
        ] {
            source.write_all(chunk).await.unwrap();
        }
        source.shutdown().await.unwrap();
        let mut received = Vec::new();
        capture.read_to_end(&mut received).await.unwrap();
        task.await.unwrap();
        assert_eq!(received, LABEL);
    }

    #[tokio::test]
    async fn empty_diagnostics_remain_empty() {
        let (source, raw) = tokio::io::duplex(32);
        let (filtered, mut capture) = tokio::io::duplex(256);
        drop(source);
        drain(raw, filtered).await;
        let mut received = Vec::new();
        capture.read_to_end(&mut received).await.unwrap();
        assert!(received.is_empty());
    }
}

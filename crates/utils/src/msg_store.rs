use std::{
    collections::VecDeque,
    sync::{Arc, RwLock},
};

use futures::{StreamExt, future};
use tokio::{sync::broadcast, task::JoinHandle};
use tokio_stream::wrappers::{BroadcastStream, errors::BroadcastStreamRecvError};

use crate::{log_msg::LogMsg, stream_lines::LinesStreamExt};

// Large default for stores that need full replay from memory (for example, on-demand
// normalization of historical logs). Live execution/event stores should generally use
// `with_limits` to keep the desktop server from buffering excessive output in-process.
const DEFAULT_HISTORY_BYTES: usize = 100000 * 1024;
const DEFAULT_CHANNEL_CAPACITY: usize = 100000;

#[derive(Clone)]
struct StoredMsg {
    msg: LogMsg,
    bytes: usize,
}

struct Inner {
    history: VecDeque<StoredMsg>,
    total_bytes: usize,
    history_bytes_limit: usize,
    history_evicted: bool,
}

pub struct MsgStore {
    inner: RwLock<Inner>,
    sender: broadcast::Sender<LogMsg>,
}

impl Default for MsgStore {
    fn default() -> Self {
        Self::new()
    }
}

impl MsgStore {
    pub fn new() -> Self {
        Self::with_limits(DEFAULT_HISTORY_BYTES, DEFAULT_CHANNEL_CAPACITY)
    }

    pub fn with_limits(history_bytes_limit: usize, channel_capacity: usize) -> Self {
        let (sender, _) = broadcast::channel(channel_capacity.max(1));
        Self {
            inner: RwLock::new(Inner {
                history: VecDeque::with_capacity(32),
                total_bytes: 0,
                history_bytes_limit,
                history_evicted: false,
            }),
            sender,
        }
    }

    pub fn push(&self, msg: LogMsg) {
        let bytes = msg.approx_bytes();

        let mut inner = self.inner.write().unwrap();
        while inner.total_bytes.saturating_add(bytes) > inner.history_bytes_limit {
            if let Some(front) = inner.history.pop_front() {
                inner.history_evicted = true;
                inner.total_bytes = inner.total_bytes.saturating_sub(front.bytes);
            } else {
                break;
            }
        }
        inner.history.push_back(StoredMsg { msg, bytes });
        inner.total_bytes = inner.total_bytes.saturating_add(bytes);
        // Capture and subscription share this lock with publication. A reader
        // sees each message in its snapshot OR its live receiver, never neither.
        let _ = self.sender.send(inner.history.back().unwrap().msg.clone());
    }

    // Convenience
    pub fn push_stdout<S: Into<String>>(&self, s: S) {
        self.push(LogMsg::Stdout(s.into()));
    }

    pub fn push_patch(&self, patch: json_patch::Patch) {
        self.push(LogMsg::JsonPatch(patch));
    }

    pub fn push_session_id(&self, session_id: String) {
        self.push(LogMsg::SessionId(session_id));
    }

    pub fn push_message_id(&self, id: String) {
        self.push(LogMsg::MessageId(id));
    }

    pub fn push_finished(&self) {
        self.push(LogMsg::Finished);
    }

    pub fn get_receiver(&self) -> broadcast::Receiver<LogMsg> {
        self.sender.subscribe()
    }

    pub fn get_history(&self) -> Vec<LogMsg> {
        self.inner
            .read()
            .unwrap()
            .history
            .iter()
            .map(|s| s.msg.clone())
            .collect()
    }

    /// Finite integrity replay after the producer has stopped. No recovery from
    /// dropped history; callers must fail closed instead of certifying a prefix.
    pub fn get_history_strict(&self) -> std::io::Result<Vec<LogMsg>> {
        let inner = self.inner.read().unwrap();
        if inner.history_evicted {
            return Err(std::io::Error::other(
                "MsgStore history evicted before capture",
            ));
        }
        Ok(inner.history.iter().map(|s| s.msg.clone()).collect())
    }

    /// History then live, as `LogMsg`.
    pub fn history_plus_stream(
        &self,
    ) -> futures::stream::BoxStream<'static, Result<LogMsg, std::io::Error>> {
        let (history, rx) = (self.get_history(), self.get_receiver());

        let hist = futures::stream::iter(history.into_iter().map(Ok::<_, std::io::Error>));
        let live = BroadcastStream::new(rx).filter_map(|res| async move {
            match res {
                Ok(msg) => Some(Ok(msg)),
                Err(BroadcastStreamRecvError::Lagged(n)) => {
                    tracing::error!(
                        skipped = n,
                        "MsgStore broadcast lagged. {n} messages dropped for this subscriber"
                    );
                    None
                }
            }
        });

        Box::pin(hist.chain(live))
    }

    /// Lossless snapshot-to-live capture. Reject pre-subscription eviction and
    /// live receiver lag; neither can certify a complete durable log.
    pub fn history_plus_stream_strict(
        &self,
    ) -> futures::stream::BoxStream<'static, Result<LogMsg, std::io::Error>> {
        self.capture(true)
    }

    /// UI recovery retains the surviving history after eviction, while still
    /// reporting live lag. This is deliberately NOT a review integrity proof.
    pub fn history_plus_stream_recoverable(
        &self,
    ) -> futures::stream::BoxStream<'static, Result<LogMsg, std::io::Error>> {
        self.capture(false)
    }

    fn capture(
        &self,
        require_full_history: bool,
    ) -> futures::stream::BoxStream<'static, Result<LogMsg, std::io::Error>> {
        let inner = self.inner.read().unwrap();
        if require_full_history && inner.history_evicted {
            return futures::stream::once(async {
                Err(std::io::Error::other(
                    "MsgStore history evicted before capture",
                ))
            })
            .boxed();
        }
        let rx = self.sender.subscribe();
        let history: Vec<_> = inner.history.iter().map(|s| s.msg.clone()).collect();
        drop(inner);
        let hist = futures::stream::iter(history.into_iter().map(Ok::<_, std::io::Error>));
        let live = BroadcastStream::new(rx).map(|res| match res {
            Ok(msg) => Ok(msg),
            Err(BroadcastStreamRecvError::Lagged(n)) => Err(std::io::Error::other(format!(
                "MsgStore broadcast lagged; {n} messages dropped"
            ))),
        });
        Box::pin(hist.chain(live))
    }

    pub fn stdout_chunked_stream(
        &self,
    ) -> futures::stream::BoxStream<'static, Result<String, std::io::Error>> {
        self.history_plus_stream()
            .take_while(|res| future::ready(!matches!(res, Ok(LogMsg::Finished))))
            .filter_map(|res| async move {
                match res {
                    Ok(LogMsg::Stdout(s)) => Some(Ok(s)),
                    _ => None,
                }
            })
            .boxed()
    }

    pub fn stdout_lines_stream(
        &self,
    ) -> futures::stream::BoxStream<'static, std::io::Result<String>> {
        self.stdout_chunked_stream().lines()
    }

    pub fn stderr_chunked_stream(
        &self,
    ) -> futures::stream::BoxStream<'static, Result<String, std::io::Error>> {
        self.history_plus_stream()
            .take_while(|res| future::ready(!matches!(res, Ok(LogMsg::Finished))))
            .filter_map(|res| async move {
                match res {
                    Ok(LogMsg::Stderr(s)) => Some(Ok(s)),
                    _ => None,
                }
            })
            .boxed()
    }

    /// Forward a stream of typed log messages into this store.
    pub fn spawn_forwarder<S, E>(self: Arc<Self>, stream: S) -> JoinHandle<()>
    where
        S: futures::Stream<Item = Result<LogMsg, E>> + Send + 'static,
        E: std::fmt::Display + Send + 'static,
    {
        tokio::spawn(async move {
            tokio::pin!(stream);

            while let Some(next) = stream.next().await {
                match next {
                    Ok(msg) => self.push(msg),
                    Err(e) => self.push(LogMsg::Stderr(format!("stream error: {e}"))),
                }
            }
        })
    }
}

#[cfg(test)]
mod review_tests {
    use super::*;

    #[tokio::test]
    async fn review_capture_has_no_snapshot_subscription_gap_or_duplicates() {
        for _ in 0..50 {
            let store = Arc::new(MsgStore::with_limits(1024 * 1024, 2048));
            let writer = store.clone();
            let thread = std::thread::spawn(move || {
                for n in 0..1000 {
                    writer.push_stdout(n.to_string());
                }
                writer.push_finished();
            });
            let mut capture = store.history_plus_stream_strict();
            for n in 0..1000 {
                let message =
                    tokio::time::timeout(std::time::Duration::from_secs(2), capture.next())
                        .await
                        .unwrap()
                        .unwrap()
                        .unwrap();
                assert!(matches!(message, LogMsg::Stdout(s) if s==n.to_string()));
            }
            assert!(matches!(capture.next().await, Some(Ok(LogMsg::Finished))));
            thread.join().unwrap();
        }
    }
    #[tokio::test]
    async fn review_capture_rejects_live_lag() {
        let store = MsgStore::with_limits(1024, 1);
        let mut capture = store.history_plus_stream_strict();
        store.push_stdout("a");
        store.push_stdout("b");
        store.push_finished();
        assert!(capture.next().await.unwrap().is_err());
    }
    #[tokio::test]
    async fn review_strictness_keeps_ui_history_recovery_available() {
        let store = MsgStore::with_limits(1, 4);
        store.push_stdout("evicted report");
        store.push_finished();
        assert!(
            store
                .history_plus_stream_strict()
                .next()
                .await
                .unwrap()
                .is_err()
        );
        assert!(matches!(
            store.history_plus_stream_recoverable().next().await,
            Some(Ok(LogMsg::Finished))
        ));
    }

    #[test]
    fn review_snapshot_rejects_evicted_history_forever() {
        let store = MsgStore::with_limits(1, 4);
        store.push_stdout("report");
        store.push_finished();
        assert!(store.get_history_strict().is_err());
        store.push_stdout("another");
        assert!(store.get_history_strict().is_err());
        // Recovery readers still retain the surviving history.
        assert!(!store.get_history().is_empty());
    }
}

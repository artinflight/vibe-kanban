use std::{
    collections::VecDeque,
    sync::{Arc, Mutex, RwLock},
};

use futures::{StreamExt, future};
use tokio::{
    sync::{broadcast, mpsc},
    task::JoinHandle,
};
use tokio_stream::wrappers::{BroadcastStream, ReceiverStream, errors::BroadcastStreamRecvError};

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
    durable_sender: Option<mpsc::Sender<std::io::Result<LogMsg>>>,
    durable_receiver: Mutex<Option<mpsc::Receiver<std::io::Result<LogMsg>>>>,
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
            durable_sender: None,
            durable_receiver: Mutex::new(None),
        }
    }

    /// One bounded raw capture consumer, independent of the lossy UI broadcast.
    /// The producer awaits capacity before publishing; slow storage backpressures
    /// the pipe instead of dropping a suffix of a large thread/resume response.
    pub fn with_durable_capture(history_bytes: usize, ui_capacity: usize, capacity: usize) -> Self {
        let mut store = Self::with_limits(history_bytes, ui_capacity);
        let (tx, rx) = mpsc::channel(capacity.max(1));
        store.durable_sender = Some(tx);
        store.durable_receiver = Mutex::new(Some(rx));
        store
    }

    pub fn has_durable_capture(&self) -> bool {
        self.durable_sender.is_some()
    }

    pub fn take_durable_capture(&self) -> Option<ReceiverStream<std::io::Result<LogMsg>>> {
        self.durable_receiver
            .lock()
            .unwrap()
            .take()
            .map(ReceiverStream::new)
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
        // Metadata Finished must not fall between snapshot and subscription.
        // Publication holds the write lock; keep both reads in one boundary.
        let inner = self.inner.read().unwrap();
        let rx = self.sender.subscribe();
        let history: Vec<_> = inner.history.iter().map(|s| s.msg.clone()).collect();
        drop(inner);

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
                    Ok(msg) => {
                        if let Some(tx) = &self.durable_sender
                            && tx.send(Ok(msg.clone())).await.is_err()
                        {
                            self.push(LogMsg::Stderr("Durable raw capture unavailable".into()));
                            return;
                        }
                        self.push(msg);
                    }
                    Err(e) => {
                        if let Some(tx) = &self.durable_sender {
                            let _ = tx
                                .send(Err(std::io::Error::other(format!(
                                    "Raw source failed: {e}"
                                ))))
                                .await;
                        }
                        self.push(LogMsg::Stderr(format!("stream error: {e}")));
                        return;
                    }
                }
            }
            if let Some(tx) = &self.durable_sender {
                let _ = tx.send(Ok(LogMsg::Finished)).await;
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
            for strict in [false, true] {
                let store = Arc::new(MsgStore::with_limits(1024 * 1024, 2048));
                let writer = store.clone();
                let thread = std::thread::spawn(move || {
                    for n in 0..1000 {
                        writer.push_stdout(n.to_string());
                    }
                    writer.push_finished();
                });
                let mut capture = if strict {
                    store.history_plus_stream_strict()
                } else {
                    store.history_plus_stream()
                };
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

#[cfg(test)]
mod durable_capture_tests {
    use super::*;
    #[tokio::test]
    async fn slow_capture_survives_ui_lag_and_eviction_and_delayed_subscription() {
        let store = Arc::new(MsgStore::with_durable_capture(64, 2, 2));
        let mut capture = store.take_durable_capture().unwrap();
        assert!(store.take_durable_capture().is_none(), "one writer only");
        let mut ui = store.history_plus_stream_strict();
        let mut expected = vec![LogMsg::Stdout("resume prefix".into())];
        expected.extend((0..5000).map(|_| LogMsg::Stdout("x".repeat(4096))));
        expected.push(LogMsg::Stdout("assistant final — ✓\n".into()));
        let source = expected.clone();
        let producer = store.clone().spawn_forwarder(futures::stream::iter(
            source.into_iter().map(Ok::<_, std::io::Error>),
        ));
        tokio::task::yield_now().await;
        assert!(
            !producer.is_finished(),
            "bounded queue backpressures producer"
        );
        let mut actual = vec![];
        while let Some(msg) = capture.next().await {
            match msg.unwrap() {
                LogMsg::Finished => break,
                msg => actual.push(msg),
            }
            tokio::task::yield_now().await;
        }
        producer.await.unwrap();
        assert_eq!(
            serde_json::to_string(&actual).unwrap(),
            serde_json::to_string(&expected).unwrap()
        );
        assert!(
            store.get_history_strict().is_err(),
            "UI eviction is not a raw loss"
        );
        assert!(
            ui.next().await.unwrap().is_err(),
            "exercise actual broadcast lag"
        );
    }
    #[tokio::test]
    async fn source_error_is_not_successful_closure() {
        let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 2));
        let mut capture = store.take_durable_capture().unwrap();
        let producer = store.clone().spawn_forwarder(futures::stream::iter([
            Ok(LogMsg::Stdout("prefix".into())),
            Err(std::io::Error::other("source read failed")),
        ]));
        assert!(matches!(
            capture.next().await.unwrap().unwrap(),
            LogMsg::Stdout(_)
        ));
        assert!(capture.next().await.unwrap().is_err());
        producer.await.unwrap();
        assert!(
            tokio::time::timeout(std::time::Duration::from_millis(5), capture.next())
                .await
                .is_err(),
            "no invented Finished"
        );
    }
    #[tokio::test]
    async fn disconnected_writer_stops_producer_without_claiming_closure() {
        let store = Arc::new(MsgStore::with_durable_capture(1024, 2, 1));
        drop(store.take_durable_capture().unwrap());
        let producer = store.clone().spawn_forwarder(futures::stream::iter([Ok::<
            _,
            std::io::Error,
        >(
            LogMsg::Stdout("must capture".into()),
        )]));
        producer.await.unwrap();
        assert!(
            !store
                .get_history()
                .iter()
                .any(|m| matches!(m, LogMsg::Finished))
        );
    }
}

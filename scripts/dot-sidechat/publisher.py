"""Injected-transport publisher. This module contains no network implementation."""
from sidechat import Principal


def publish_once(store, owner, deliver):
    """deliver is the trusted existing verified-subscription transport, never a URL from a message."""
    principal = Principal(owner, "publisher")
    job = store.claim(principal)
    if job is None:
        return None
    try:
        status = deliver(job["subscription"], job["event"])
    except Exception:
        status = 0  # Lost response: receipt remains unconfirmed and the stable event may be retried.
    store.acknowledge(principal, job["event"]["eventId"], job["attempt"], status)
    return {"event_id": job["event"]["eventId"], "attempt": job["attempt"], "http_status": status}

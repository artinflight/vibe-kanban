#!/usr/bin/env python3
"""Independent restart monitor. Only allowlisted local assets and GET APIs."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time

from legacy import LegacySource
from estimates import forecast
from progress import Measurements, atomic_json, read_json, validate

ASSETS = Path(__file__).with_name("web")


class Monitor:
    def __init__(self, config, cache):
        self.config, self.cache = config, Path(cache)
        self.measurements = Measurements()
        self.lock = threading.Lock()
        self.latest, self.error = None, None
        self.source = LegacySource(config) if config["source"] == "legacy" else None
        try:
            self.latest = validate(read_json(self.cache))
            if self.latest.get("run_id") != config.get("run_id"):
                self.latest = None
        except (OSError, ValueError):
            pass

    def poll(self):
        try:
            source = self.source.snapshot() if self.source else read_json(self.config["progress_file"])
            if source.get("run_id") != self.config["run_id"]:
                raise ValueError("Selected attempt does not match progress")
            result = self.measurements.project(source)
            with self.lock:
                changed = (not self.latest or source["updated_at"] != self.latest["updated_at"]
                           or source["run_id"] != self.latest["run_id"]
                           or result["estimate_policy"] != self.latest.get("estimate_policy"))
                if changed:
                    # Persist the public projection only; never the raw receipts.
                    atomic_json(self.cache, result)
                self.latest, self.error = result, None
        except (OSError, ValueError, KeyError, TypeError, StopIteration):
            with self.lock:
                self.error = "Controller updates unavailable. Showing the last saved observation; retrying automatically."

    def response(self):
        with self.lock:
            result = dict(self.latest) if self.latest else dict(
                schema=1, status="idle", title="Vibe restart", steps=[], events=[], errors=[], blockers=[],
                percent=0, completed_steps=0, remaining_steps=0, skipped_steps=0, eta_seconds=None,
                current_step=None, started_at=None, updated_at=None,
            )
            result["served_at"] = time.time()
            result["source_error"] = self.error
            result["stale"] = bool(self.error) or (
                result.get("status") not in {"completed", "failed", "idle"}
                and time.time() - result.get("updated_at", 0) > result.get("stale_after_seconds", 30))
            if result["stale"]:
                result["eta_seconds"] = None
                result["steps"] = [dict(s, eta_seconds=None, rate_per_second=None) for s in result["steps"]]
            result["estimate"] = forecast(result, result["served_at"])
            return result


def handler(monitor):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            route = self.path.split("?", 1)[0]
            if route == "/api/status":
                data, mime = json.dumps(monitor.response(), allow_nan=False).encode(), "application/json"
            elif route == "/healthz":
                data, mime = b'{"ok":true}', "application/json"
            elif route in {"/", "/app.js", "/style.css"}:
                name, mime = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                              "/style.css": ("style.css", "text/css")}[route]
                data = ASSETS.joinpath(name).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_HEAD(self):
            self.send_response(200 if self.path in {"/", "/healthz", "/api/status"} else 404)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8189)
    args = parser.parse_args()
    monitor = Monitor(read_json(args.config), args.cache)
    monitor.poll()

    def poll():
        while True:
            time.sleep(2)
            monitor.poll()

    threading.Thread(target=poll, daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), handler(monitor))
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()

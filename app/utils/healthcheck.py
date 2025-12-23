"""
Lightweight healthcheck HTTP server for Render.
Uses standard library only.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import time
from threading import Thread
from typing import Optional, Tuple

from app.utils.runtime_state import runtime_state

_START_TIME = time.time()


class _HealthcheckHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/health", "/healthz"):
            mode = "active"
            reason = None
            if runtime_state.lock_acquired is False:
                mode = "passive"
                reason = "singleton_lock"
            payload = {
                "status": "ok",
                "mode": mode,
                "reason": reason,
                "singleton_lock": runtime_state.lock_acquired,
                "storage": runtime_state.storage_mode,
                "kie_mode": "stub" if os.getenv("KIE_STUB", "0") == "1" else "real",
                "uptime": int(time.time() - _START_TIME),
                "last_error": runtime_state.last_error,
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def start_healthcheck_server(port: int) -> Tuple[ThreadingHTTPServer, Thread]:
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthcheckHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop_healthcheck_server(server: Optional[ThreadingHTTPServer]) -> None:
    if not server:
        return
    server.shutdown()
    server.server_close()

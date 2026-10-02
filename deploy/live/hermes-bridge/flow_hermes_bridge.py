#!/usr/bin/env python3
"""Host-side bridge: approved FLOW-AS handoffs -> Erik's existing Hermes.

Listens on the docker0 address only (default 172.17.0.1:18790), requires a
bearer token, and runs `hermes -z` with limited toolsets in the background.
It never changes Hermes config and never restarts the Hermes gateway.
"""

from __future__ import annotations

import datetime
import hmac
import json
import os
import pathlib
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("BRIDGE_HOST", "172.17.0.1")
PORT = int(os.environ.get("BRIDGE_PORT", "18790"))
TOKEN = os.environ.get("HERMES_BRIDGE_TOKEN", "")
HERMES_BIN = os.environ.get("HERMES_BIN", "/usr/local/bin/hermes")
TOOLSETS = os.environ.get("HERMES_BRIDGE_TOOLSETS", "web,memory,skills,todo")
TIMEOUT = int(os.environ.get("HERMES_BRIDGE_TIMEOUT", "900"))
STATE = pathlib.Path(os.environ.get("BRIDGE_STATE_DIR", "/var/lib/flow-hermes-bridge"))
REF_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
MAX_BODY = 64 * 1024
RUN_LOCK = threading.Semaphore(1)


def now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def write(path: pathlib.Path, data: dict) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def run_job(ref: str, prompt: str) -> None:
    path = STATE / f"{ref}.json"
    with RUN_LOCK:
        job = json.loads(path.read_text())
        job.update(status="running", started=now())
        write(path, job)
        usage = STATE / f"{ref}.usage.json"
        try:
            proc = subprocess.run(
                [HERMES_BIN, "-z", prompt, "-t", TOOLSETS, "--usage-file", str(usage)],
                capture_output=True, text=True, timeout=TIMEOUT, cwd="/root", check=False,
            )
            job.update(
                status="done" if proc.returncode == 0 else "failed",
                exit_code=proc.returncode,
                output=(proc.stdout or "")[-20000:],
                error=(proc.stderr or "")[-4000:] if proc.returncode else "",
            )
        except subprocess.TimeoutExpired:
            job.update(status="timeout")
        except Exception as exc:  # pragma: no cover
            job.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        job["finished"] = now()
        write(path, job)
        print(f"flow-hermes-bridge: job {ref} {job['status']}", flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "FlowHermesBridge/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        return len(TOKEN) >= 24 and hmac.compare_digest(supplied.encode(), f"Bearer {TOKEN}".encode())

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"ok": True, "service": "flow-hermes-bridge", "toolsets": TOOLSETS})
            return
        match = re.fullmatch(r"/handoff/([A-Za-z0-9_-]{4,64})", self.path)
        if match and self._authorized():
            path = STATE / f"{match.group(1)}.json"
            if path.exists():
                job = json.loads(path.read_text())
                job.pop("prompt", None)
                self._send(200, {"ok": True, "job": job})
                return
            self._send(404, {"ok": False, "error": "not found"})
            return
        self._send(401 if match else 404, {"ok": False, "error": "unauthorized" if match else "not found"})

    def do_POST(self) -> None:
        if self.path != "/handoff":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._authorized():
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0 or length > MAX_BODY:
            self._send(413, {"ok": False, "error": "body size"})
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad json"})
            return
        ref = str(payload.get("ref") or "")
        prompt = str(payload.get("prompt") or "").strip()
        if not REF_RE.match(ref) or not prompt:
            self._send(400, {"ok": False, "error": "ref and prompt required"})
            return
        path = STATE / f"{ref}.json"
        if path.exists():
            self._send(200, {"ok": True, "status": "already_queued", "job": ref})
            return
        write(path, {"ref": ref, "status": "queued", "queued": now(), "toolsets": TOOLSETS, "prompt": prompt})
        threading.Thread(target=run_job, args=(ref, prompt), daemon=True).start()
        print(f"flow-hermes-bridge: queued {ref}", flush=True)
        self._send(202, {"ok": True, "status": "queued", "job": ref})

    def log_message(self, fmt: str, *args) -> None:
        print(f"flow-hermes-bridge: {self.address_string()} {fmt % args}", flush=True)


if __name__ == "__main__":
    if len(TOKEN) < 24:
        raise SystemExit("HERMES_BRIDGE_TOKEN must be set (24+ chars)")
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    print(f"flow-hermes-bridge listening on {HOST}:{PORT} toolsets={TOOLSETS}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

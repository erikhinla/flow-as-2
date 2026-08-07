"""Internal HTTP adapter for the official NousResearch Hermes Agent image."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = "0.0.0.0"
PORT = int(os.getenv("FLOW_RUNTIME_PORT", "18789"))
MODEL = os.getenv("HERMES_AGENT_MODEL", "openai/gpt-5.6-terra")
ALLOWED_MODELS = {
    "openai/gpt-5.6-luna",
    "openai/gpt-5.6-terra",
    "openai/gpt-5.6-sol",
    "anthropic/claude-sonnet-5",
}
UPSTREAM_REPOSITORY = "https://github.com/NousResearch/hermes-agent"
UPSTREAM_COMMIT = os.getenv("HERMES_UPSTREAM_COMMIT", "unknown")


def hermes_version() -> str:
    result = subprocess.run(
        ["hermes", "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    output = (result.stdout or result.stderr).strip()
    if result.returncode != 0:
        raise RuntimeError(output or f"hermes --version exited {result.returncode}")
    return output


def _clean_csv(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def run_hermes(
    prompt: str,
    *,
    model: str,
    toolsets: list[str],
    skills: list[str],
) -> dict[str, object]:
    if model not in ALLOWED_MODELS:
        raise ValueError(f"model '{model}' is not approved for Hermes")

    usage_handle = tempfile.NamedTemporaryFile(
        prefix="hermes-usage-",
        suffix=".json",
        delete=False,
    )
    usage_path = usage_handle.name
    usage_handle.close()
    command = [
        "hermes",
        "--provider",
        "openrouter",
        "--model",
        model,
        "--usage-file",
        usage_path,
    ]
    if toolsets:
        command.extend(["--toolsets", ",".join(toolsets)])
    if skills:
        command.extend(["--skills", ",".join(skills)])
    command.extend(["--oneshot", prompt])

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=int(os.getenv("FLOW_RUNTIME_TIMEOUT_SECONDS", "900")),
        check=False,
        cwd="/workspace",
    )
    try:
        output = result.stdout.strip()
        usage: dict[str, object] = {}
        try:
            with open(usage_path, "r", encoding="utf-8") as usage_file:
                usage = json.load(usage_file)
        except (OSError, json.JSONDecodeError):
            usage = {}
        if result.returncode != 0:
            error = result.stderr.strip() or output
            raise RuntimeError(error or f"Hermes exited {result.returncode}")
        if not output:
            raise RuntimeError("Hermes returned an empty response")
        used_model = str(usage.get("model") or model)
        if used_model.replace("openrouter/", "", 1) != model:
            raise RuntimeError(
                f"Hermes model mismatch: selected {model}, reported {used_model}"
            )
        return {
            "final": output,
            "model": model,
            "provider": "openrouter",
            "execution_mode": "hermes_agent",
            "toolsets": toolsets,
            "skills": skills,
            "usage": usage,
        }
    finally:
        try:
            os.unlink(usage_path)
        except OSError:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = "FLOWHermesAdapter/1.0"

    def _send(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path not in {"/health", "/healthz"}:
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            version = hermes_version()
            self._send(
                200,
                {
                    "ok": True,
                    "engine": "hermes",
                    "version": version,
                    "default_model": MODEL,
                    "allowed_models": sorted(ALLOWED_MODELS),
                    "official_agent_only": True,
                    "upstream_repository": UPSTREAM_REPOSITORY,
                    "upstream_commit": UPSTREAM_COMMIT,
                },
            )
        except Exception as exc:
            self._send(503, {"ok": False, "engine": "hermes", "error": str(exc)})

    def do_POST(self) -> None:
        if self.path != "/run":
            self._send(404, {"ok": False, "error": "not found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length) or b"{}")
            prompt = str(payload.get("prompt") or "").strip()
            if not prompt:
                self._send(400, {"ok": False, "error": "prompt is required"})
                return
            model = str(payload.get("model") or MODEL).strip()
            toolsets = _clean_csv(payload.get("toolsets"))
            skills = _clean_csv(payload.get("skills"))
            result = run_hermes(
                prompt,
                model=model,
                toolsets=toolsets,
                skills=skills,
            )
            self._send(
                200,
                {
                    "ok": True,
                    "engine": "hermes",
                    **result,
                    "upstream_repository": UPSTREAM_REPOSITORY,
                    "upstream_commit": UPSTREAM_COMMIT,
                },
            )
        except subprocess.TimeoutExpired:
            self._send(504, {"ok": False, "engine": "hermes", "error": "execution timed out"})
        except Exception as exc:
            self._send(500, {"ok": False, "engine": "hermes", "error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        print(f"hermes-runner: {format % args}", flush=True)


if __name__ == "__main__":
    print(
        f"Hermes Agent adapter listening on {HOST}:{PORT} "
        f"(upstream {UPSTREAM_COMMIT})",
        flush=True,
    )
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

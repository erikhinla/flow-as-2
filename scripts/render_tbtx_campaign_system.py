#!/usr/bin/env python3
"""Build a complete TBTX campaign proof, not a single generated image."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import signal
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any
from urllib.parse import urlencode


PROFILE = "tbtx_campaign_system_v1"
CONCEPT = "Everything works. Nothing moves."
DIALS = {"design_variance": 9, "visual_density": 5, "motion_intensity": 8}


def load_production_plan(path: Path) -> dict[str, Any]:
    plan = json.loads(path.read_text(encoding="utf-8"))
    if plan.get("schema") != "faas.creative_production_plan":
        raise RuntimeError("Production plan has the wrong schema")
    if plan.get("primary_mode") != "campaign":
        raise RuntimeError("Production plan must use Campaign Mode")
    copy = plan.get("copy")
    if not isinstance(copy, dict):
        raise RuntimeError("Production plan is missing copy decisions")
    return plan


def _html_line(value: object) -> str:
    return html.escape(str(value or "").strip(), quote=True)


def _js_line(value: object) -> str:
    return json.dumps(str(value or "").strip(), ensure_ascii=False)


def apply_production_plan(plan: dict[str, Any]) -> dict[str, str]:
    """Apply the producing agent's decisions to every campaign surface."""
    copy = plan["copy"]
    headline = _html_line(copy["homepage_headline"]).replace("\n", "<br>")
    home = HOME.replace("Everything works.<br>Nothing moves.", headline)
    home = home.replace(
        "Your tools report activity. Your day keeps paying for the missing operating layer.",
        _html_line(copy["homepage_lede"]),
    )
    home = home.replace(
        "The dashboard sees output. It can't see the handoff.",
        _html_line(copy["evidence_line"]),
    )
    home = home.replace(
        "Fog is how it feels. Friction is what it costs.",
        _html_line(copy["friction_headline"]),
        1,
    )
    home = home.replace(
        "The gap between information, ownership, and action is where momentum disappears. Diagnose the gap before adding another tool.",
        _html_line(copy["friction_body"]),
    )

    diagnostic = DIAGNOSTIC.replace(
        "Where does momentum disappear first?",
        _html_line(copy["diagnostic_question"]),
    )

    social = SOCIAL.replace(
        "YOUR TABS AREN'T THE PROBLEM.",
        _html_line(copy["personal_social_title"]),
    ).replace(
        "The missing path between information and action keeps stealing your momentum.",
        _html_line(copy["personal_social_copy"]),
    )
    social = social.replace(
        "title.textContent = 'EVERY HANDOFF IS A TAX.'",
        f"title.textContent = {_js_line(copy['business_social_title'])}",
    ).replace(
        'copy.textContent = "When context doesn\'t travel, the work pays twice."',
        f"copy.textContent = {_js_line(copy['business_social_copy'])}",
    )
    social = social.replace(
        'title.textContent = "YOU CAN\'T AUTOMATE A MESS."',
        f"title.textContent = {_js_line(copy['doctrine_social_title'])}",
    ).replace(
        "copy.textContent = 'Diagnose the operating layer first.'",
        f"copy.textContent = {_js_line(copy['doctrine_social_copy'])}",
    )

    motion = MOTION.replace(
        "EVERYTHING WORKS.",
        _html_line(copy["motion_scene_one_title"]),
        1,
    ).replace(
        "The tools agree.",
        _html_line(copy["motion_scene_one_copy"]),
        1,
    )
    motion = motion.replace(
        "title.textContent = 'NOTHING MOVES.'",
        f"title.textContent = {_js_line(copy['motion_scene_two_title'])}",
    ).replace(
        "copy.textContent = 'The handoff keeps rebuilding the truth.'",
        f"copy.textContent = {_js_line(copy['motion_scene_two_copy'])}",
    )
    motion = motion.replace(
        "title.textContent = 'FIND THE FRICTION.'",
        f"title.textContent = {_js_line(copy['motion_scene_three_title'])}",
    ).replace(
        "copy.textContent = 'Fog is how it feels. Friction is what it costs.'",
        f"copy.textContent = {_js_line(copy['motion_scene_three_copy'])}",
    )
    return {
        "index.html": home,
        "diagnostic.html": diagnostic,
        "result.html": RESULT,
        "social.html": social,
        "motion.html": motion,
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, timeout: int = 360) -> None:
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "command failed")[-4_000:]
        raise RuntimeError(detail)


def probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    payload = json.loads(completed.stdout)
    streams = payload.get("streams") or []
    visual = next((item for item in streams if item.get("codec_type") == "video"), {})
    return {
        "width": int(visual.get("width") or 0),
        "height": int(visual.get("height") or 0),
        "duration": round(float((payload.get("format") or {}).get("duration") or 0), 3),
        "has_audio": any(item.get("codec_type") == "audio" for item in streams),
    }


def mean_audio_db(path: Path) -> float:
    completed = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    match = re.search(r"mean_volume:\s*(-?[0-9.]+)\s*dB", completed.stderr)
    if not match:
        raise RuntimeError("Campaign film audio level could not be measured")
    return float(match.group(1))


def find_browser() -> str:
    candidates = (
        os.getenv("CHROMIUM_BIN", ""),
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    )
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(candidate, os.X_OK):
            return candidate
    discovered = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
    if discovered:
        return discovered
    raise RuntimeError("Chromium or Google Chrome is required for real browser captures")


@contextmanager
def serve_directory(directory: Path):
    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            return

    handler = partial(QuietHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def screenshot(
    browser: str,
    page: str | Path,
    output: Path,
    width: int,
    height: int,
    params: dict[str, str] | None = None,
) -> None:
    url = str(page)
    if not url.startswith(("http://", "https://")):
        url = Path(url).resolve().as_uri()
    if params:
        url += "?" + urlencode(params)
    with tempfile.TemporaryDirectory(prefix="faas-chrome-") as profile:
        command = [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--force-dark-mode",
            "--hide-scrollbars",
            "--allow-file-access-from-files",
            "--autoplay-policy=no-user-gesture-required",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            "--virtual-time-budget=1800",
            f"--screenshot={output.resolve()}",
            url,
        ]
        output.unlink(missing_ok=True)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 30
        try:
            while time.monotonic() < deadline:
                if output.is_file() and output.stat().st_size > 0:
                    break
                if process.poll() is not None:
                    _, stderr = process.communicate(timeout=2)
                    raise RuntimeError(
                        "Chromium exited before creating the capture: "
                        + (stderr or f"exit {process.returncode}")[-2_000:]
                    )
                time.sleep(0.1)
            else:
                raise RuntimeError(f"Chromium timed out creating {output.name}")
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=3)
    facts = probe(output)
    if (facts["width"], facts["height"]) != (width, height):
        resized = output.with_suffix(".resized.png")
        run(["ffmpeg", "-y", "-i", str(output), "-vf", f"scale={width}:{height}", "-frames:v", "1", str(resized)])
        resized.replace(output)


def write(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


CSS = r"""
:root {
  color-scheme: dark light;
  --canvas: #101215;
  --surface: #171a1e;
  --surface-2: #20242a;
  --ink: #eef0ec;
  --muted: #a9afb1;
  --line: rgba(238,240,236,.18);
  --hairline: rgba(238,240,236,.08);
  --signal: #9fbd91;
  --signal-ink: #111712;
  --shadow: rgba(0,0,0,.48);
  --font-display: "Arial Narrow", "DejaVu Sans Condensed", sans-serif;
  --font-body: "Helvetica Neue", Arial, sans-serif;
  --font-mono: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: light) {
  :root {
    --canvas: #e8e9e6;
    --surface: #f4f5f2;
    --surface-2: #dadeda;
    --ink: #171a1d;
    --muted: #4d5458;
    --line: rgba(23,26,29,.22);
    --hairline: rgba(23,26,29,.1);
    --signal: #5f8057;
    --signal-ink: #f5f7f3;
    --shadow: rgba(39,44,48,.2);
  }
}
* { box-sizing: border-box; }
html { max-width: 100%; overflow-x: clip; background: var(--canvas); scroll-behavior: smooth; }
body { margin: 0; min-width: 320px; max-width: 100%; overflow-x: clip; background: var(--canvas); color: var(--ink); font-family: var(--font-body); }
a { color: inherit; }
button, a { -webkit-tap-highlight-color: transparent; }
button { font: inherit; }
.noise { position: fixed; inset: 0; z-index: 20; pointer-events: none; opacity: .06; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 180 180' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.78' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.65'/%3E%3C/svg%3E"); }
.rail { height: 68px; display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 24px; padding: 0 clamp(20px, 4vw, 64px); border-bottom: 1px solid var(--line); position: relative; z-index: 4; }
.rail-title { font: 700 12px/1 var(--font-mono); letter-spacing: .08em; text-decoration: none; white-space: nowrap; }
.rail nav { display: flex; align-items: center; gap: 28px; white-space: nowrap; }
.rail nav a { color: var(--muted); font: 600 12px/1 var(--font-body); text-decoration: none; }
.rail nav a:hover, .rail nav a:focus-visible { color: var(--ink); }
.hero { min-height: calc(100dvh - 68px); display: grid; grid-template-columns: minmax(0,.86fr) minmax(520px,1.14fr); align-items: stretch; }
.hero-copy { min-width: 0; display: flex; flex-direction: column; justify-content: center; padding: clamp(54px, 7vw, 108px) clamp(24px, 5.3vw, 86px); position: relative; z-index: 2; }
.status { display: inline-flex; align-items: center; gap: 10px; width: fit-content; margin-bottom: 30px; color: var(--signal); font: 700 11px/1 var(--font-mono); letter-spacing: .11em; text-transform: uppercase; }
.lamp { width: 11px; height: 11px; background: var(--signal); box-shadow: 0 0 0 5px color-mix(in srgb, var(--signal) 12%, transparent); }
h1, h2, p { margin-top: 0; }
h1 { max-width: 760px; margin-bottom: 24px; font: 800 clamp(52px, 6.1vw, 100px)/.86 var(--font-display); letter-spacing: -.055em; text-transform: uppercase; }
.lede { max-width: 510px; margin-bottom: 36px; color: var(--muted); font-size: clamp(16px, 1.3vw, 20px); line-height: 1.45; }
.actions { display: flex; align-items: center; gap: 13px; flex-wrap: wrap; }
.button { display: inline-flex; align-items: center; justify-content: center; min-height: 48px; padding: 0 22px; border: 1px solid var(--ink); background: var(--ink); color: var(--canvas); font-weight: 760; text-decoration: none; white-space: nowrap; cursor: pointer; transition: transform .25s cubic-bezier(.16,1,.3,1), background .25s ease, color .25s ease; }
.button:hover { transform: translateY(-2px); }
.button:active { transform: translateY(1px) scale(.985); }
.button.secondary { border-color: var(--line); background: transparent; color: var(--ink); }
.button.secondary:hover { background: var(--surface-2); }
.hero-media { min-width: 0; padding: clamp(24px, 3vw, 48px) clamp(20px, 4vw, 64px) clamp(24px, 3vw, 48px) 0; display: flex; align-items: center; }
.bezel { position: relative; width: 100%; min-height: 72vh; overflow: hidden; border: 1px solid rgba(255,255,255,.28); background: var(--surface); box-shadow: inset 0 0 0 8px rgba(255,255,255,.025), inset 0 0 0 9px var(--line), 0 42px 90px var(--shadow); }
.bezel video, .bezel img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: saturate(.66) contrast(1.1) brightness(.66); }
.bezel::before { content: ""; position: absolute; inset: 0; z-index: 1; opacity: .38; background: linear-gradient(90deg, transparent 0 11.8%, rgba(159,189,145,.5) 11.9% 12%, transparent 12.1% 72%, rgba(159,189,145,.34) 72.1% 72.25%, transparent 72.35%), repeating-linear-gradient(0deg, transparent 0 43px, rgba(238,240,236,.1) 44px, transparent 45px); clip-path: polygon(0 0,100% 0,100% 76%,72% 76%,72% 100%,0 100%); }
.bezel::after { content: ""; position: absolute; inset: 0; z-index: 1; background: linear-gradient(90deg, rgba(16,18,21,.18), transparent 52%), linear-gradient(0deg, rgba(16,18,21,.72), transparent 46%); }
.instrument { position: absolute; z-index: 3; top: 26px; right: 26px; display: grid; grid-template-columns: auto auto; gap: 5px 18px; padding: 12px 14px; border: 1px solid rgba(238,240,236,.38); color: #dce4da; background: rgba(11,14,16,.42); backdrop-filter: blur(8px); font: 700 10px/1.2 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; }
.instrument b { color: var(--signal); font-weight: 700; }
.evidence { position: absolute; left: clamp(22px, 3vw, 48px); right: clamp(22px, 3vw, 48px); bottom: clamp(22px, 3vw, 46px); z-index: 2; display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: end; }
.evidence strong { display: block; max-width: 560px; font: 800 clamp(26px, 3.2vw, 52px)/.94 var(--font-display); letter-spacing: -.035em; text-transform: uppercase; }
.evidence dl { margin: 0; font: 700 11px/1.7 var(--font-mono); }
.evidence dt { color: var(--muted); }
.evidence dd { margin: 0 0 8px; }
.friction-band { display: grid; grid-template-columns: 1.25fr .75fr; min-height: 72vh; border-top: 1px solid var(--line); }
.friction-copy { padding: clamp(70px, 9vw, 140px) clamp(24px, 8vw, 130px); }
.friction-copy h2 { max-width: 820px; font: 800 clamp(44px, 6vw, 94px)/.92 var(--font-display); letter-spacing: -.045em; text-transform: uppercase; }
.friction-copy p { max-width: 610px; color: var(--muted); font-size: 19px; line-height: 1.5; }
.source-evidence { position: relative; width: min(520px,100%); height: 104px; margin: 42px 0 0; display: grid; grid-template-columns: 1fr 1fr; gap: 1px; overflow: hidden; border: 1px solid var(--line); background: var(--line); }
.source-evidence img { width: 100%; height: 100%; object-fit: cover; filter: saturate(.38) contrast(1.18) brightness(.46); }
.source-evidence figcaption { position: absolute; inset: auto 12px 10px auto; padding: 6px 8px; color: var(--signal); background: rgba(11,14,16,.72); font: 700 9px/1 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; }
.fault-map { border-left: 1px solid var(--line); display: grid; grid-template-rows: repeat(4,1fr); }
.fault { display: grid; grid-template-columns: 58px 1fr; align-items: center; gap: 20px; padding: 24px 34px; border-bottom: 1px solid var(--hairline); }
.fault:last-child { border-bottom: 0; }
.fault b { color: var(--signal); font: 700 14px/1 var(--font-mono); }
.fault span { font: 700 clamp(18px, 2vw, 29px)/1 var(--font-display); text-transform: uppercase; }
.page-shell { min-height: calc(100dvh - 68px); display: grid; grid-template-columns: minmax(0,.7fr) minmax(480px,1.3fr); }
.page-context { padding: clamp(46px, 6vw, 96px); display: flex; flex-direction: column; justify-content: space-between; border-right: 1px solid var(--line); background: linear-gradient(160deg, var(--surface), var(--canvas)); }
.page-context h1 { font-size: clamp(50px, 5.8vw, 88px); }
.page-context p { max-width: 410px; color: var(--muted); line-height: 1.5; }
.route-switch { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid var(--line); }
.route-switch button { min-height: 48px; border: 0; border-right: 1px solid var(--line); background: transparent; color: var(--muted); cursor: pointer; }
.route-switch button:last-child { border-right: 0; }
.route-switch button.active { background: var(--signal); color: var(--signal-ink); font-weight: 800; }
.diagnostic-panel { padding: clamp(46px, 7vw, 110px); display: flex; flex-direction: column; justify-content: center; }
.progress { display: flex; gap: 8px; margin-bottom: 40px; }
.progress i { display: block; width: 54px; height: 3px; background: var(--surface-2); }
.progress i.on { background: var(--signal); }
.question { max-width: 760px; font: 800 clamp(38px, 4.4vw, 68px)/.96 var(--font-display); letter-spacing: -.035em; text-transform: uppercase; }
.answers { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin: 36px 0 28px; background: var(--line); border: 1px solid var(--line); }
.answer { min-height: 112px; padding: 24px; border: 0; background: var(--canvas); color: var(--ink); text-align: left; cursor: pointer; transition: transform .2s ease, background .2s ease, color .2s ease; }
.answer:hover, .answer:focus-visible { background: var(--surface-2); }
.answer.selected { background: var(--signal); color: var(--signal-ink); }
.answer:active { transform: scale(.985); }
.answer strong { display: block; margin-bottom: 8px; font-size: 17px; }
.answer span { color: inherit; opacity: .72; font-size: 14px; line-height: 1.35; }
.form-error { min-height: 22px; color: #d7aaa3; font-size: 14px; }
.loading { display: none; gap: 10px; margin: 22px 0; }
.loading.on { display: grid; }
.loading i { height: 12px; background: var(--surface-2); animation: breathe 1s ease-in-out infinite alternate; }
.loading i:nth-child(2) { width: 76%; animation-delay: .12s; }
.result-stage { min-height: calc(100dvh - 68px); display: grid; grid-template-columns: minmax(0,1.05fr) minmax(430px,.95fr); }
.result-copy { padding: clamp(54px, 8vw, 124px); display: flex; flex-direction: column; justify-content: center; }
.result-copy h1 { font-size: clamp(54px, 7.5vw, 116px); max-width: 980px; }
.result-copy .lede { max-width: 660px; }
.result-proof { margin-top: 34px; display: grid; grid-template-columns: repeat(2,1fr); gap: 1px; background: var(--line); border: 1px solid var(--line); }
.result-proof div { padding: 22px; background: var(--canvas); }
.result-proof b { display: block; margin-bottom: 8px; color: var(--signal); font: 700 11px/1 var(--font-mono); text-transform: uppercase; }
.result-proof span { line-height: 1.35; }
.result-visual { position: relative; overflow: hidden; min-height: 650px; }
.result-visual img { width: 100%; height: 100%; object-fit: cover; filter: saturate(.56) contrast(1.12) brightness(.6); }
.result-visual::before { content: ""; position: absolute; inset: 0; z-index: 1; background: repeating-linear-gradient(90deg, transparent 0 79px, rgba(159,189,145,.12) 80px, transparent 81px), repeating-linear-gradient(0deg, transparent 0 79px, rgba(238,240,236,.08) 80px, transparent 81px); }
.result-visual::after { content: ""; position: absolute; inset: 0; z-index: 1; box-shadow: inset 28px 0 80px var(--canvas); }
.social { min-height: 100dvh; position: relative; overflow: hidden; display: grid; background: var(--canvas); }
.social-media { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: saturate(.58) contrast(1.15) brightness(.5); }
.social::before { content: ""; position: absolute; inset: 3.8%; z-index: 1; border: 1px solid rgba(238,240,236,.2); background: linear-gradient(90deg, transparent 0 18%, rgba(159,189,145,.35) 18.1% 18.25%, transparent 18.35%), repeating-linear-gradient(0deg, transparent 0 89px, rgba(238,240,236,.075) 90px, transparent 91px); clip-path: polygon(0 0,84% 0,84% 8%,100% 8%,100% 100%,0 100%); }
.social::after { content: ""; position: absolute; inset: 0; background: linear-gradient(0deg, rgba(16,18,21,.96), rgba(16,18,21,.05) 66%), linear-gradient(90deg, rgba(16,18,21,.72), transparent); }
.social-copy { z-index: 2; align-self: end; padding: clamp(42px, 8vw, 108px); }
.social-copy h1 { max-width: 900px; font-size: clamp(58px, 10vw, 138px); }
.social-copy p { max-width: 600px; color: #d2d6d2; font-size: clamp(18px, 2.4vw, 28px); line-height: 1.35; }
.social-mark { position: absolute; z-index: 3; top: clamp(30px, 5vw, 72px); left: clamp(30px, 6vw, 86px); display: flex; gap: 12px; align-items: center; color: var(--signal); font: 700 clamp(12px, 1.6vw, 20px)/1 var(--font-mono); letter-spacing: .08em; text-transform: uppercase; }
.social.business .social-copy { align-self: center; padding-right: 42%; }
.social.business::after { background: linear-gradient(90deg, rgba(16,18,21,.97) 0 44%, rgba(16,18,21,.16) 76%); }
.social.story .social-copy { padding-bottom: 14vh; }
.social.story .social-copy h1 { font-size: clamp(82px, 15vw, 180px); }
.motion { min-height: 100dvh; position: relative; overflow: hidden; display: flex; align-items: center; background: var(--canvas); }
.motion img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: saturate(.52) contrast(1.2) brightness(.45); }
.motion::before { content: ""; position: absolute; inset: 5vh 3vw; z-index: 1; border: 1px solid rgba(238,240,236,.22); background: linear-gradient(90deg, transparent 0 21%, rgba(159,189,145,.42) 21.1% 21.2%, transparent 21.3% 68%, rgba(238,240,236,.16) 68.1% 68.2%, transparent 68.3%), repeating-linear-gradient(0deg, transparent 0 119px, rgba(238,240,236,.07) 120px, transparent 121px); clip-path: polygon(0 0,78% 0,78% 7%,100% 7%,100% 100%,0 100%); }
.motion::after { content: ""; position: absolute; inset: 0; background: linear-gradient(90deg, rgba(16,18,21,.96), rgba(16,18,21,.1) 74%); }
.motion-copy { position: relative; z-index: 2; width: 76%; padding-left: 7vw; }
.motion-copy h1 { font-size: clamp(90px, 10vw, 190px); }
.motion-copy p { color: #d6dad5; font: 600 28px/1.3 var(--font-body); }
@keyframes breathe { to { opacity: .42; } }
@media (prefers-reduced-motion: no-preference) {
  .hero-copy > * { animation: rise .8s cubic-bezier(.16,1,.3,1) both; }
  .hero-copy > *:nth-child(2) { animation-delay: .08s; }
  .hero-copy > *:nth-child(3) { animation-delay: .16s; }
  .hero-copy > *:nth-child(4) { animation-delay: .24s; }
  .bezel { animation: settle 1.15s cubic-bezier(.16,1,.3,1) both; }
}
@keyframes rise { from { opacity: 0; transform: translateY(22px); } }
@keyframes settle { from { opacity: 0; transform: translateX(32px) scale(.985); } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
@media (max-width: 767px) {
  .rail { height: 58px; padding: 0 18px; }
  .rail-title { font-size: 10px; }
  .rail nav { gap: 15px; }
  .rail nav a { font-size: 11px; }
  .hero, .page-shell, .result-stage { min-height: calc(100dvh - 58px); grid-template-columns: 1fr; }
  .hero-copy { min-height: 0; padding: 40px 20px 28px; }
  .status { margin-bottom: 16px; }
  h1 { max-width: 100%; font-size: clamp(44px, 13.2vw, 54px); }
  .hero-copy h1 { margin-bottom: 18px; }
  .hero-copy .lede { margin-bottom: 24px; }
  .hero-media { padding: 0 20px 20px; }
  .bezel { min-height: 320px; }
  .evidence { grid-template-columns: 1fr; }
  .evidence strong { font-size: 24px; }
  .evidence dl { display: none; }
  .instrument { top: 14px; right: 14px; padding: 9px 10px; font-size: 8px; }
  .friction-band { grid-template-columns: 1fr; }
  .friction-copy { padding: 74px 20px; }
  .fault-map { border-left: 0; border-top: 1px solid var(--line); }
  .fault { padding: 20px; }
  .page-context { padding: 24px 20px; border-right: 0; border-bottom: 1px solid var(--line); }
  .page-context h1 { margin-bottom: 16px; font-size: 40px; }
  .page-context > div:first-child p { display: none; }
  .route-switch button { min-height: 42px; }
  .diagnostic-panel { padding: 28px 20px 32px; }
  .progress { margin-bottom: 22px; }
  .question { font-size: 32px; }
  .answers { grid-template-columns: repeat(2,minmax(0,1fr)); margin: 24px 0 18px; }
  .answer { min-height: 96px; padding: 15px; }
  .answer strong { font-size: 14px; }
  .answer span { font-size: 12px; }
  .result-copy { min-height: calc(100dvh - 58px); padding: 42px 20px; background: linear-gradient(90deg, rgba(16,18,21,.94), rgba(16,18,21,.76)), url("assets/field-b.jpg") center/cover; }
  .result-copy h1 { font-size: 48px; }
  .result-proof { grid-template-columns: 1fr; }
  .result-proof div { padding: 16px; }
  .result-visual { display: none; }
  .social-copy { padding: 44px; }
  .social-copy h1 { font-size: 86px; }
  .social.business .social-copy { padding-right: 8vw; }
}
"""


JS = r"""
(() => {
  const state = { route: new URLSearchParams(location.search).get('type') || 'tbtx', answer: '' };
  const routeButtons = [...document.querySelectorAll('[data-route]')];
  const answerButtons = [...document.querySelectorAll('[data-answer]')];
  const continueButton = document.querySelector('[data-continue]');
  const error = document.querySelector('[data-error]');
  const loading = document.querySelector('[data-loading]');

  const renderRoute = () => {
    routeButtons.forEach((button) => button.classList.toggle('active', button.dataset.route === state.route));
    const routeName = document.querySelector('[data-route-name]');
    if (routeName) routeName.textContent = state.route === 'bizbuilders' ? 'Your business' : 'Your day';
  };
  routeButtons.forEach((button) => button.addEventListener('click', () => {
    state.route = button.dataset.route;
    renderRoute();
  }));
  answerButtons.forEach((button) => button.addEventListener('click', () => {
    state.answer = button.dataset.answer;
    answerButtons.forEach((candidate) => candidate.classList.toggle('selected', candidate === button));
    if (error) error.textContent = '';
    if (loading) {
      loading.classList.add('on');
      setTimeout(() => loading.classList.remove('on'), 520);
    }
  }));
  if (continueButton) continueButton.addEventListener('click', () => {
    if (!state.answer) {
      if (error) error.textContent = 'Choose the place where momentum breaks first.';
      return;
    }
    location.href = `result.html?type=${encodeURIComponent(state.route)}&signal=${encodeURIComponent(state.answer)}`;
  });
  renderRoute();

  const resultTitle = document.querySelector('[data-result-title]');
  if (resultTitle) {
    const business = state.route === 'bizbuilders';
    resultTitle.textContent = business ? 'HANDOFF DEBT.' : 'CONTEXT SWITCHING.';
    document.querySelector('[data-result-kicker]').textContent = business ? 'Your friction pattern' : 'Your fog pattern';
    document.querySelector('[data-result-copy]').textContent = business
      ? 'The work is moving, but truth and ownership are being rebuilt at every handoff.'
      : 'Your attention is doing the routing work your tools were supposed to carry.';
    const cta = document.querySelector('[data-result-cta]');
    cta.textContent = business ? 'Build the foundation' : 'Clear the fog';
    cta.href = business ? 'https://transformby10x.ai/bizbuilders-ai/' : 'https://transformby10x.ai/foglift-kit.html';
    document.querySelector('[data-proof-one]').textContent = business ? 'Context is recovered before work can continue.' : 'You keep deciding where to look next.';
    document.querySelector('[data-proof-two]').textContent = business ? 'Ownership blurs between people and tools.' : 'Small handoffs keep breaking your focus.';
  }
})();
"""


def page_document(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="theme-color" content="#101215">
  <title>{title}</title>
  <link rel="stylesheet" href="campaign.css">
</head>
<body>
{body}
<div class="noise" aria-hidden="true"></div>
<script src="campaign.js"></script>
</body>
</html>"""


HEADER = """<header class="rail">
  <a class="rail-title" href="index.html">DIGITAL FOG / DIGITAL FRICTION</a>
  <nav aria-label="Campaign">
    <a href="diagnostic.html?type=tbtx">Personal</a>
    <a href="diagnostic.html?type=bizbuilders">Business</a>
  </nav>
</header>"""


HOME = page_document(
    "Everything works. Nothing moves.",
    HEADER
    + """<main>
  <section class="hero">
    <div class="hero-copy">
      <div class="status"><span class="lamp" aria-hidden="true"></span>System status: green</div>
      <h1>Everything works.<br>Nothing moves.</h1>
      <p class="lede">Your tools report activity. Your day keeps paying for the missing operating layer.</p>
      <div class="actions"><a class="button" href="diagnostic.html">Find the blockage</a></div>
    </div>
    <div class="hero-media">
      <figure class="bezel">
        <img src="assets/field-a.jpg" alt="A physically constructed routing instrument with a luminous signal interrupted at the handoff">
        <div class="instrument" aria-hidden="true"><span>Signal</span><b>Green</b><span>Context</span><b>Lost</b></div>
        <figcaption class="evidence">
          <strong>The dashboard sees output. It can't see the handoff.</strong>
          <dl><dt>REPORTED</dt><dd>ACTIVE</dd><dt>EXPERIENCED</dt><dd>STUCK</dd></dl>
        </figcaption>
      </figure>
    </div>
  </section>
  <section class="friction-band">
    <div class="friction-copy">
      <h2>Fog is how it feels. Friction is what it costs.</h2>
      <p>The gap between information, ownership, and action is where momentum disappears. Diagnose the gap before adding another tool.</p>
      <figure class="source-evidence"><img src="assets/source-evidence-a.jpg" alt="Personal digital fog source evidence"><img src="assets/source-evidence-b.jpg" alt="Business digital friction source evidence"><figcaption>Activity visible / handoff missing</figcaption></figure>
    </div>
    <div class="fault-map" aria-label="Common friction signals">
      <div class="fault"><b>A</b><span>Find the truth</span></div>
      <div class="fault"><b>B</b><span>Know the owner</span></div>
      <div class="fault"><b>C</b><span>Carry the context</span></div>
      <div class="fault"><b>D</b><span>Prove the result</span></div>
    </div>
  </section>
</main>""",
)


DIAGNOSTIC = page_document(
    "Find where momentum breaks",
    HEADER
    + """<main class="page-shell">
  <aside class="page-context">
    <div><div class="status"><span class="lamp" aria-hidden="true"></span>Diagnostic entry</div><h1 data-route-name>Your day</h1><p>Pick the lane. The questions stay human. The routing changes with the consequence.</p></div>
    <div class="route-switch" aria-label="Choose diagnostic lane">
      <button type="button" data-route="tbtx">Personal</button><button type="button" data-route="bizbuilders">Business</button>
    </div>
  </aside>
  <section class="diagnostic-panel">
    <div class="progress" aria-label="Question 1 of 3"><i class="on"></i><i></i><i></i></div>
    <h1 class="question">Where does momentum disappear first?</h1>
    <div class="answers">
      <button class="answer" type="button" data-answer="find"><strong>Finding what matters</strong><span>I know it exists. I don't know where.</span></button>
      <button class="answer" type="button" data-answer="trust"><strong>Trusting the information</strong><span>I keep checking whether the answer is current.</span></button>
      <button class="answer" type="button" data-answer="handoff"><strong>Handing work over</strong><span>The next person has to rebuild the context.</span></button>
      <button class="answer" type="button" data-answer="finish"><strong>Finishing the work</strong><span>Activity rises. The result keeps slipping.</span></button>
    </div>
    <div class="loading" data-loading aria-label="Loading next question"><i></i><i></i></div>
    <div class="form-error" data-error role="alert"></div>
    <div><button class="button" type="button" data-continue>See the pattern</button></div>
  </section>
</main>""",
)


RESULT = page_document(
    "Your diagnostic result",
    HEADER
    + """<main class="result-stage">
  <section class="result-copy">
    <div class="status"><span class="lamp" aria-hidden="true"></span><span data-result-kicker>Your fog pattern</span></div>
    <h1 data-result-title>CONTEXT SWITCHING.</h1>
    <p class="lede" data-result-copy>Your attention is doing the routing work your tools were supposed to carry.</p>
    <div class="actions"><a class="button" data-result-cta href="https://transformby10x.ai/foglift-kit.html">Clear the fog</a><a class="button secondary" href="diagnostic.html">Check another signal</a></div>
    <div class="result-proof"><div><b>What happens</b><span data-proof-one>You keep deciding where to look next.</span></div><div><b>What it creates</b><span data-proof-two>Small handoffs keep breaking your focus.</span></div></div>
  </section>
  <aside class="result-visual"><img src="assets/field-b.jpg" alt="A fabricated architectural corridor where layered handoffs resolve into one clear path"><div class="instrument" aria-hidden="true"><span>Route</span><b>Found</b><span>Owner</span><b>Pending</b></div></aside>
</main>""",
)


SOCIAL = page_document(
    "Campaign placement",
    """<main class="social" data-social-root>
  <img class="social-media" data-social-image src="assets/field-a.jpg" alt="A real work environment under digital pressure">
  <div class="social-mark"><span class="lamp" aria-hidden="true"></span><span data-social-mark>Digital Fog</span></div>
  <div class="social-copy"><h1 data-social-title>YOUR TABS AREN'T THE PROBLEM.</h1><p data-social-copy>The missing path between information and action keeps stealing your momentum.</p></div>
</main>
<script>
  const placement = new URLSearchParams(location.search).get('placement') || 'personal';
  const root = document.querySelector('[data-social-root]');
  const title = document.querySelector('[data-social-title]');
  const copy = document.querySelector('[data-social-copy]');
  const mark = document.querySelector('[data-social-mark]');
  const image = document.querySelector('[data-social-image]');
  if (placement === 'business') {
    root.classList.add('business'); title.textContent = 'EVERY HANDOFF IS A TAX.'; copy.textContent = "When context doesn't travel, the work pays twice."; mark.textContent = 'Digital Friction'; image.src = 'assets/field-b.jpg';
  }
  if (placement === 'story') {
    root.classList.add('story'); title.textContent = "YOU CAN'T AUTOMATE A MESS."; copy.textContent = 'Diagnose the operating layer first.'; mark.textContent = 'Architecture over tools'; image.src = 'assets/field-a.jpg';
  }
</script>""",
)


MOTION = page_document(
    "Campaign motion frame",
    """<main class="motion">
  <img data-motion-image src="assets/field-a.jpg" alt="Campaign evidence">
  <div class="motion-copy"><div class="status"><span class="lamp" aria-hidden="true"></span><span data-motion-status>System status: green</span></div><h1 data-motion-title>EVERYTHING WORKS.</h1><p data-motion-copy>The tools agree.</p></div>
</main>
<script>
  const scene = new URLSearchParams(location.search).get('scene') || 'one';
  const title = document.querySelector('[data-motion-title]');
  const copy = document.querySelector('[data-motion-copy]');
  const status = document.querySelector('[data-motion-status]');
  const image = document.querySelector('[data-motion-image]');
  if (scene === 'two') { title.textContent = 'NOTHING MOVES.'; copy.textContent = 'The handoff keeps rebuilding the truth.'; status.textContent = 'Lived status: stuck'; image.src = 'assets/field-b.jpg'; }
  if (scene === 'three') { title.textContent = 'FIND THE FRICTION.'; copy.textContent = 'Fog is how it feels. Friction is what it costs.'; status.textContent = 'Start with the blockage'; image.src = 'assets/field-a.jpg'; }
</script>""",
)


def validate_copy(site: Path, primary_line: str = CONCEPT) -> dict[str, str]:
    visible_sources = [site / "index.html", site / "diagnostic.html", site / "result.html", site / "social.html", site / "motion.html"]
    joined = "\n".join(path.read_text(encoding="utf-8") for path in visible_sources)
    checks = {
        "zero_em_dash": "PASS" if "—" not in joined and "–" not in joined else "FAIL",
        "no_generic_ai_hype": "PASS" if not any(word in joined.lower() for word in ("unlock", "supercharge", "revolutionary", "seamless", "next-gen")) else "FAIL",
        "no_logo_header": "PASS" if "logo" not in HEADER.lower() and "wordmark" not in HEADER.lower() else "FAIL",
        "one_primary_concept": "PASS" if primary_line.lower() in (site / "index.html").read_text(encoding="utf-8").lower() else "FAIL",
        "reduced_motion": "PASS" if "prefers-reduced-motion: reduce" in (site / "campaign.css").read_text(encoding="utf-8") else "FAIL",
        "viewport_stability": "PASS" if "100dvh" in (site / "campaign.css").read_text(encoding="utf-8") else "FAIL",
    }
    failed = [name for name, status in checks.items() if status != "PASS"]
    if failed:
        raise RuntimeError("Anti-slop page gate failed: " + ", ".join(failed))
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--source-a", required=True)
    parser.add_argument("--source-b", required=True)
    parser.add_argument("--material-a", required=True)
    parser.add_argument("--material-b", required=True)
    parser.add_argument("--production-plan", required=True)
    args = parser.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")
    browser = find_browser()
    workspace = Path(args.workspace).resolve()
    source_a = Path(args.source_a).resolve()
    source_b = Path(args.source_b).resolve()
    material_a = Path(args.material_a).resolve()
    material_b = Path(args.material_b).resolve()
    production_plan_path = Path(args.production_plan).resolve()
    for source in (source_a, source_b, material_a, material_b):
        if not source.is_file():
            raise RuntimeError(f"Campaign source not found: {source}")
    if not production_plan_path.is_file():
        raise RuntimeError(f"Creative production plan not found: {production_plan_path}")
    production_plan = load_production_plan(production_plan_path)
    planned_copy = production_plan["copy"]
    planned_dials = production_plan.get("dials") or DIALS

    site = workspace / "campaign"
    assets = site / "assets"
    captures = workspace / "captures"
    social = workspace / "social"
    motion = workspace / "motion"
    for directory in (assets, captures, social, motion):
        directory.mkdir(parents=True, exist_ok=True)

    source_frames = (
        (source_a, assets / "source-evidence-a.jpg", "crop=1200:675:40:405,scale=960:540"),
        (source_b, assets / "source-evidence-b.jpg", "crop=1200:675:360:405,scale=960:540"),
    )
    for source, target, framing in source_frames:
        run([
            "ffmpeg", "-y", "-ss", "1.2", "-i", str(source),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase," + framing,
            "-frames:v", "1", "-q:v", "2", str(target),
        ])
    for material, target in (
        (material_a, assets / "field-a.jpg"),
        (material_b, assets / "field-b.jpg"),
    ):
        run([
            "ffmpeg", "-y", "-i", str(material),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
            "-frames:v", "1", "-q:v", "2", str(target),
        ])

    write(site / "campaign.css", CSS)
    write(site / "campaign.js", JS)
    planned_pages = apply_production_plan(production_plan)
    for filename, content in planned_pages.items():
        write(site / filename, content)

    capture_specs = (
        (site / "index.html", captures / "homepage-desktop.png", 1440, 900, None),
        (site / "index.html", captures / "homepage-mobile.png", 390, 844, None),
        (site / "diagnostic.html", captures / "diagnostic-desktop.png", 1440, 900, {"type": "bizbuilders"}),
        (site / "diagnostic.html", captures / "diagnostic-mobile.png", 390, 844, {"type": "tbtx"}),
        (site / "result.html", captures / "result-desktop.png", 1440, 900, {"type": "bizbuilders", "signal": "handoff"}),
        (site / "result.html", captures / "result-mobile.png", 390, 844, {"type": "tbtx", "signal": "find"}),
    )
    social_specs = (
        (social / "personal-instagram-1080x1350.png", 1080, 1350, "personal"),
        (social / "business-linkedin-1200x627.png", 1200, 627, "business"),
        (social / "doctrine-story-1080x1920.png", 1080, 1920, "story"),
    )
    scene_paths: list[Path] = []
    with serve_directory(site) as origin:
        for page, output, width, height, params in capture_specs:
            screenshot(browser, f"{origin}/{page.name}", output, width, height, params)
        for output, width, height, placement in social_specs:
            screenshot(browser, f"{origin}/social.html", output, width, height, {"placement": placement})
        for scene in ("one", "two", "three"):
            output = motion / f"scene-{scene}.png"
            screenshot(browser, f"{origin}/motion.html", output, 1920, 1080, {"scene": scene})
            scene_paths.append(output)

    film = motion / "campaign-film-15s.mp4"
    filter_graph = (
        "[0:v]zoompan=z='min(zoom+0.00018,1.027)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080:fps=30[v0];"
        "[1:v]zoompan=z='min(zoom+0.00016,1.024)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080:fps=30[v1];"
        "[2:v]zoompan=z='min(zoom+0.0002,1.03)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1920x1080:fps=30[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0,format=yuv420p[v];"
        "[3:a]volume=1.2,lowpass=f=180,tremolo=f=0.25:d=0.55,afade=t=in:st=0:d=0.5,afade=t=out:st=14:d=1[a]"
    )
    run([
        "ffmpeg", "-y",
        "-framerate", "30", "-i", str(scene_paths[0]),
        "-framerate", "30", "-i", str(scene_paths[1]),
        "-framerate", "30", "-i", str(scene_paths[2]),
        "-f", "lavfi", "-i", "sine=frequency=52:sample_rate=48000:duration=15",
        "-filter_complex", filter_graph,
        "-map", "[v]", "-map", "[a]", "-t", "15",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(film),
    ], timeout=600)

    contact = workspace / "campaign-contact-sheet.png"
    run([
        "ffmpeg", "-y", "-i", str(scene_paths[0]), "-i", str(scene_paths[1]), "-i", str(scene_paths[2]),
        "-filter_complex", "[0:v]scale=640:360[a];[1:v]scale=640:360[b];[2:v]scale=640:360[c];[a][b][c]hstack=inputs=3[out]",
        "-map", "[out]", "-frames:v", "1", str(contact),
    ])

    anti_slop_checks = validate_copy(
        site,
        str(planned_copy["homepage_headline"]),
    )
    film_facts = probe(film)
    if (film_facts["width"], film_facts["height"]) != (1920, 1080):
        raise RuntimeError("Campaign film must be exactly 1920x1080")
    if abs(float(film_facts["duration"]) - 15.0) > 0.15:
        raise RuntimeError("Campaign film must be exactly 15 seconds")
    if not film_facts["has_audio"]:
        raise RuntimeError("Campaign film must contain intentional audio")
    film_facts["mean_audio_db"] = mean_audio_db(film)
    if float(film_facts["mean_audio_db"]) < -32.0:
        raise RuntimeError("Campaign film audio is technically present but functionally inaudible")
    with tempfile.TemporaryDirectory(prefix="faas-film-check-") as check_dir:
        check_frames: list[Path] = []
        for index, timestamp in enumerate((2, 7, 12), start=1):
            frame = Path(check_dir) / f"story-{index}.jpg"
            run([
                "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(film),
                "-frames:v", "1", "-q:v", "3", str(frame),
            ])
            check_frames.append(frame)
        if len({sha256(frame) for frame in check_frames}) != 3:
            raise RuntimeError("Campaign film does not progress through three distinct story states")

    expected_dimensions = {
        "captures/homepage-desktop.png": (1440, 900),
        "captures/homepage-mobile.png": (390, 844),
        "captures/diagnostic-desktop.png": (1440, 900),
        "captures/diagnostic-mobile.png": (390, 844),
        "captures/result-desktop.png": (1440, 900),
        "captures/result-mobile.png": (390, 844),
        "social/personal-instagram-1080x1350.png": (1080, 1350),
        "social/business-linkedin-1200x627.png": (1200, 627),
        "social/doctrine-story-1080x1920.png": (1080, 1920),
    }
    for relative, dimensions in expected_dimensions.items():
        facts = probe(workspace / relative)
        if (facts["width"], facts["height"]) != dimensions:
            raise RuntimeError(f"Incorrect capture dimensions for {relative}")

    social_hashes = {sha256(workspace / relative) for relative in expected_dimensions if relative.startswith("social/")}
    if len(social_hashes) != 3:
        raise RuntimeError("The three social placements must be visually distinct files")

    visual_system = production_plan["visual_system"]
    write(
        workspace / "concept-brief.md",
        f"""
# {production_plan['concept']}

Primary mode: Campaign.

{production_plan['campaign_thesis']}

Audience tension: {production_plan.get('audience_tension', '')}

Material direction: {visual_system['material_direction']}

Composition logic: {visual_system['composition_logic']}

Light behavior: {visual_system['light_behavior']}

Source footage role: {visual_system['source_footage_role']}

Template rejection: {visual_system['template_rejection']}

Dials: {json.dumps(planned_dials, sort_keys=True)}
""",
    )
    write(
        workspace / "campaign-copy-map.md",
        "# Campaign copy map\n\n"
        + "\n\n".join(
            f"## {name.replace('_', ' ').title()}\n\n{value}"
            for name, value in planned_copy.items()
        ),
    )
    write(workspace / "conversion-path.md", """
# Conversion path

1. The campaign names the contradiction without selling a tool.
2. The visitor chooses Personal or Business.
3. The diagnostic locates the first break in momentum.
4. Personal fog routes to Fog-Lift.
5. Business friction routes to BizBuilders AI.
6. BizBot remains downstream until the operating layer is ready.

No logo is used in the header. The campaign idea carries the opening moment.
""")
    (workspace / "anti-slop-evidence.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "primary_mode": "campaign",
                "concept": production_plan["concept"],
                "dials": planned_dials,
                "checks": anti_slop_checks,
                "system_outputs": {
                    "working_web_moments": 3,
                    "browser_captures": 6,
                    "social_placements": 3,
                    "motion_seconds": 15,
                    "motion_audio": True,
                    "conversion_routes": ["Fog-Lift", "BizBuilders AI"],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    output_files = sorted(
        path for path in workspace.rglob("*")
        if path.is_file() and path.name != "render-manifest.json"
    )
    manifest = {
        "profile": PROFILE,
        "status": "staged_for_review",
        "published": False,
        "primary_mode": "campaign",
        "concept": production_plan["concept"],
        "dials": planned_dials,
        "creative_authority": {
            "mode": "agent_led",
            "plan_file": production_plan_path.name,
            "plan_sha256": sha256(production_plan_path),
            "production_actions": production_plan["production_actions"],
        },
        "browser": Path(browser).name,
        "film": {"file": str(film.relative_to(workspace)), **film_facts},
        "routes": {
            "homepage": "campaign/index.html",
            "diagnostic": "campaign/diagnostic.html",
            "result": "campaign/result.html",
        },
        "sources": [
            {"name": source_a.name, "sha256": sha256(source_a)},
            {"name": source_b.name, "sha256": sha256(source_b)},
            {"name": material_a.name, "sha256": sha256(material_a), "role": "physical_material_plate"},
            {"name": material_b.name, "sha256": sha256(material_b), "role": "physical_material_plate"},
        ],
        "files": [
            {
                "relative_path": str(path.relative_to(workspace)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in output_files
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (workspace / "render-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()

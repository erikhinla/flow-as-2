#!/usr/bin/env python3
"""Generate and package native-resolution 4K TBTX tech art through OpenRouter."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import shutil
import struct
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "google/gemini-3.1-flash-image"
MASTER_WIDTH = 3840
MASTER_HEIGHT = 2160


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise RuntimeError(f"Generated file is not a valid PNG: {path.name}")
    return struct.unpack(">II", header[16:24])


def image_dimensions(path: Path) -> tuple[int, int]:
    if path.suffix.lower() == ".png":
        return png_dimensions(path)
    if not shutil.which("ffprobe"):
        raise RuntimeError("ffprobe is required to validate non-PNG provider output")
    completed = subprocess.run(
        [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "json", str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError((completed.stderr or "Unable to inspect provider image")[-2_000:])
    streams = (json.loads(completed.stdout).get("streams") or [])
    if not streams:
        raise RuntimeError("Provider output contains no image stream")
    return int(streams[0].get("width") or 0), int(streams[0].get("height") or 0)


def require_native_4k(width: int, height: int) -> None:
    if width < MASTER_WIDTH or height < MASTER_HEIGHT:
        raise RuntimeError(
            "Image provider returned less than native 4K "
            f"({width}x{height}); refusing to upscale and mislabel it as 4K"
        )


def run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        detail = (completed.stderr or completed.stdout or "command failed")[-4_000:]
        raise RuntimeError(detail)


def render_derivatives(native: Path, workspace: Path) -> dict[str, Path]:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for verified production derivatives")

    master = workspace / "tbtx-4k-tech-art-master.png"
    desktop = workspace / "tbtx-tech-art-desktop.webp"
    mobile = workspace / "tbtx-tech-art-mobile.webp"
    thumbnail = workspace / "tbtx-tech-art-thumbnail.webp"

    width, height = image_dimensions(native)
    require_native_4k(width, height)
    if native.suffix.lower() == ".png" and (width, height) == (MASTER_WIDTH, MASTER_HEIGHT):
        shutil.copy2(native, master)
    else:
        run(
            [
                "ffmpeg", "-y", "-i", str(native),
                "-vf",
                "scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160",
                "-frames:v", "1", str(master),
            ]
        )

    variants = (
        (desktop, "scale=1920:1080", "88"),
        (
            mobile,
            "scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350",
            "88",
        ),
        (thumbnail, "scale=640:360", "82"),
    )
    for output, filter_graph, quality in variants:
        run(
            [
                "ffmpeg", "-y", "-i", str(master), "-vf", filter_graph,
                "-frames:v", "1", "-c:v", "libwebp", "-quality", quality,
                str(output),
            ]
        )
    return {
        "master": master,
        "desktop": desktop,
        "mobile": mobile,
        "thumbnail": thumbnail,
    }


def extract_image(payload: dict[str, Any]) -> tuple[bytes, str]:
    data = payload.get("data")
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        raise RuntimeError("OpenRouter returned no image data")
    item = data[0]
    encoded = item.get("b64_json")
    if isinstance(encoded, str) and encoded:
        if encoded.startswith("data:"):
            encoded = encoded.split(",", 1)[-1]
        return base64.b64decode(encoded), str(item.get("media_type") or "image/png")
    url = item.get("url")
    if isinstance(url, str) and url.startswith("https://"):
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read(), response.headers.get_content_type()
    raise RuntimeError("OpenRouter image response contained neither b64_json nor a safe URL")


def generate(
    *,
    prompt: str,
    references: list[Path],
    model: str,
    api_key: str,
) -> tuple[bytes, str, dict[str, Any]]:
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "resolution": "4K",
        "aspect_ratio": "16:9",
        "output_format": "png",
    }
    if references:
        body["input_references"] = [
            {"type": "image_url", "image_url": {"url": data_uri(path)}}
            for path in references[:3]
        ]
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/erikhinla/flow-as-2",
            "X-Title": "FLOW Agent AS 2.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=360) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1_000).decode("utf-8", "replace")
        raise RuntimeError(f"OpenRouter image generation failed ({exc.code}): {detail}") from exc
    image, media_type = extract_image(payload)
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    return image, media_type, usage


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--reference", action="append", default=[])
    parser.add_argument("--model", default=os.getenv("FLOW_4K_IMAGE_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    prompt_source = Path(args.prompt_file).resolve()
    references = [Path(item).resolve() for item in args.reference]
    if not prompt_source.is_file():
        raise RuntimeError(f"Prompt file not found: {prompt_source}")
    for reference in references:
        if not reference.is_file():
            raise RuntimeError(f"Reference image not found: {reference}")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")

    workspace.mkdir(parents=True, exist_ok=True)
    prompt = prompt_source.read_text(encoding="utf-8").strip()
    if len(prompt) < 80:
        raise RuntimeError("Creative prompt must contain at least 80 characters")
    saved_prompt = workspace / "creative-prompt.txt"
    saved_prompt.write_text(prompt + "\n", encoding="utf-8")

    image, media_type, usage = generate(
        prompt=prompt,
        references=references,
        model=args.model,
        api_key=api_key,
    )
    native_suffixes = {
        "image/png": ".png",
        "image/x-png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }
    suffix = native_suffixes.get(media_type)
    if not suffix:
        raise RuntimeError(f"Provider returned unsupported media type: {media_type}")
    native = workspace / f"tbtx-tech-art-native{suffix}"
    native.write_bytes(image)
    native_width, native_height = image_dimensions(native)
    require_native_4k(native_width, native_height)

    outputs = render_derivatives(native, workspace)
    files = {name: path.name for name, path in outputs.items()}
    manifest = {
        "profile": "tbtx_4k_tech_art_v1",
        "status": "staged_for_review",
        "published": False,
        "provider": "openrouter",
        "provider_media_type": media_type,
        "native_file": native.name,
        "model": args.model,
        "requested_resolution": "4K",
        "requested_aspect_ratio": "16:9",
        "native_dimensions": {"width": native_width, "height": native_height},
        "master_dimensions": {"width": MASTER_WIDTH, "height": MASTER_HEIGHT},
        "prompt_file": saved_prompt.name,
        "prompt_sha256": sha256(saved_prompt),
        "references": [
            {"name": path.name, "sha256": sha256(path)} for path in references
        ],
        "files": files,
        "sha256": {name: sha256(path) for name, path in outputs.items()},
        "usage": usage,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (workspace / "render-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()

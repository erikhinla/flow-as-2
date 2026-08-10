from __future__ import annotations

import importlib.util
import struct
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "render_tbtx_4k_tech_art.py"
SPEC = importlib.util.spec_from_file_location("render_tbtx_4k_tech_art", SCRIPT)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def write_png_header(path: Path, width: int, height: int) -> None:
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", width, height)
        + b"\x08\x06\x00\x00\x00"
    )


def test_native_4k_dimensions_are_accepted(tmp_path: Path) -> None:
    image = tmp_path / "native.png"
    write_png_header(image, 4096, 2304)
    width, height = renderer.png_dimensions(image)
    renderer.require_native_4k(width, height)
    assert (width, height) == (4096, 2304)


def test_low_resolution_output_is_never_upscaled_and_called_4k(tmp_path: Path) -> None:
    image = tmp_path / "small.png"
    write_png_header(image, 1920, 1080)
    with pytest.raises(RuntimeError, match="refusing to upscale"):
        renderer.require_native_4k(*renderer.png_dimensions(image))


def test_provider_jpeg_dimensions_are_inspected_without_relabeling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "native.jpg"
    image.write_bytes(b"jpeg-placeholder")

    class Result:
        returncode = 0
        stdout = '{"streams":[{"width":4096,"height":2304}]}'
        stderr = ""

    monkeypatch.setattr(renderer.shutil, "which", lambda _name: "/usr/bin/ffprobe")
    monkeypatch.setattr(renderer.subprocess, "run", lambda *_args, **_kwargs: Result())

    assert renderer.image_dimensions(image) == (4096, 2304)

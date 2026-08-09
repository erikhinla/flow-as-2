from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "render_tbtx_campaign_system.py"
SPEC = importlib.util.spec_from_file_location("render_tbtx_campaign_system", SCRIPT)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def test_campaign_profile_is_a_connected_system() -> None:
    assert renderer.PROFILE == "tbtx_campaign_system_v1"
    assert renderer.DIALS == {
        "design_variance": 9,
        "visual_density": 5,
        "motion_intensity": 8,
    }
    assert "Everything works" in renderer.HOME
    assert "data-answer" in renderer.DIAGNOSTIC
    assert "data-result-title" in renderer.RESULT


def test_campaign_pages_enforce_key_anti_slop_rules(tmp_path: Path) -> None:
    site = tmp_path / "campaign"
    site.mkdir()
    for filename, content in {
        "index.html": renderer.HOME,
        "diagnostic.html": renderer.DIAGNOSTIC,
        "result.html": renderer.RESULT,
        "social.html": renderer.SOCIAL,
        "motion.html": renderer.MOTION,
        "campaign.css": renderer.CSS,
    }.items():
        (site / filename).write_text(content, encoding="utf-8")
    checks = renderer.validate_copy(site)
    assert all(status == "PASS" for status in checks.values())
    assert "logo" not in renderer.HEADER.lower()

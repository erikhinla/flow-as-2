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


def test_agent_production_plan_changes_campaign_surfaces() -> None:
    copy = {
        "homepage_headline": "The system is green.\nThe work is stuck.",
        "homepage_lede": "The tools say go. Your attention keeps rebuilding the route.",
        "evidence_line": "The output exists. The ownership doesn't.",
        "friction_headline": "Fog is the feeling. Friction is the cost.",
        "friction_body": "Find the break before adding another tool.",
        "diagnostic_question": "Where does forward motion break first?",
        "personal_social_title": "YOUR TABS AREN'T THE PROBLEM.",
        "personal_social_copy": "The missing route keeps taxing your attention.",
        "business_social_title": "EVERY HANDOFF COLLECTS INTEREST.",
        "business_social_copy": "When context stops, the work gets paid for twice.",
        "doctrine_social_title": "AUTOMATION CAN'T CARRY MISSING CONTEXT.",
        "doctrine_social_copy": "Repair the operating layer first.",
        "motion_scene_one_title": "THE SYSTEM IS GREEN.",
        "motion_scene_one_copy": "Every tool reports activity.",
        "motion_scene_two_title": "THE WORK IS STUCK.",
        "motion_scene_two_copy": "The handoff keeps losing the route.",
        "motion_scene_three_title": "FIND THE BREAK.",
        "motion_scene_three_copy": "Diagnose the friction before adding software.",
    }
    pages = renderer.apply_production_plan({"copy": copy})
    assert "The system is green.<br>The work is stuck." in pages["index.html"]
    assert "Where does forward motion break first?" in pages["diagnostic.html"]
    assert "EVERY HANDOFF COLLECTS INTEREST." in pages["social.html"]
    assert "THE WORK IS STUCK." in pages["motion.html"]

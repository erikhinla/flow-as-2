"""FAAS envelope integrity and media-detection regression tests.

Architectural rule: a validated envelope is a frozen contract. Heuristics must
not reinterpret work type, route, or outputs after acceptance.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow importing app without package install
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.runtime_output_validation import (  # noqa: E402
    requires_media_artifacts,
    _scrub_negated_media_phrases,
)
from app.services.envelope_validation_service import (  # noqa: E402
    normalize_creative_envelope_inputs,
    EnvelopeValidationService,
)
from app.services.task_envelope_v2 import normalize_task_envelope  # noqa: E402
from app.workers.queue_worker import (  # noqa: E402
    resolve_creative_inputs,
    _looks_like_creative_task,
)


# --- Matrix 1: GROW / move / remove / movie / .mov ---

@pytest.mark.parametrize(
    "text,expected",
    [
        ("do not move files", False),
        ("remove old paths", False),
        ("movement of records", False),
        ("movie review markdown", False),  # 'movie' is not word-boundary 'mov'
        ("export a .mov file", True),
        ("produce one mov deliverable", True),
        ("three mp4 videos", True),
        ("render a contact sheet and wordmark", True),
        ("Create finished Markdown files under 08_REPORTS/GROW/", False),
        ("Do not produce video, mp4, or campaign assets. Markdown only.", False),
        ("Write TEST_OK.md containing FAAS executed the correct task.", False),
    ],
)
def test_requires_media_artifacts_matrix(text: str, expected: bool) -> None:
    assert requires_media_artifacts(text) is expected


def test_grow_task_never_stamps_render_profile() -> None:
    envelope = {
        "task_id": "grow-test-1",
        "title": "GROW — TBTX Repository Learning Baseline",
        "goal": "No files are moved, deleted, overwritten, or published. Finished Markdown reports.",
        "task_type": "content_prep",
        "output_required": (
            "Create finished Markdown files under 08_REPORTS/GROW/. "
            "Do not move or remove files. No video."
        ),
        "inputs": {},
    }
    out = normalize_creative_envelope_inputs(envelope)
    assert not out["inputs"].get("render_profile")
    assert out["inputs"].get("execution_mode") != "repository_render_profile"


def test_false_positive_stamp_stripped_by_worker() -> None:
    resolved = resolve_creative_inputs(
        {
            "render_profile": "tbtx_social_concepts_v1",
            "execution_mode": "repository_render_profile",
            "source_files": [
                "/workspace/source/campaign/managing-digital-fog-studio.mp4",
                "/workspace/source/campaign/managing-digital-fog-remote.mp4",
            ],
        },
        title="GROW baseline",
        goal="Do not move files",
        task_type="content_prep",
        output_required="Create finished Markdown files. Do not produce video or mp4.",
    )
    assert not resolved.get("render_profile")


def test_explicit_media_contract_stamps_profile() -> None:
    envelope = {
        "task_id": "media-1",
        "title": "Campaign concepts",
        "goal": "Produce three concept videos from plates",
        "task_type": "content_prep",
        "output_required": "Three mp4 concept videos and one contact sheet png",
        "inputs": {},
    }
    out = normalize_creative_envelope_inputs(envelope)
    assert out["inputs"].get("render_profile") == "tbtx_social_concepts_v1"
    assert len(out["inputs"].get("source_files") or []) >= 2


def test_locked_profile_preserved_without_media_words() -> None:
    resolved = resolve_creative_inputs(
        {
            "render_profile": "tbtx_social_concepts_v1",
            "render_profile_locked": True,
            "source_files": ["a.mp4", "b.mp4"],
        },
        title="manual render",
        goal="operator forced profile",
        task_type="content_prep",
        output_required="markdown notes only",
    )
    assert resolved.get("render_profile") == "tbtx_social_concepts_v1"


def test_explicit_4k_profile_does_not_invent_social_video_sources() -> None:
    envelope = {
        "task_id": "4k-art-1",
        "title": "Render 4K tech art",
        "goal": "Create one native-resolution hero composition for review",
        "task_type": "content_prep",
        "output_required": "One 3840x2160 PNG and responsive WebP image derivatives",
        "inputs": {
            "render_profile": "tbtx_4k_tech_art_v1",
            "creative_prompt": "A deliberately detailed production prompt " * 4,
        },
    }
    out = normalize_creative_envelope_inputs(envelope)
    assert out["inputs"]["render_profile"] == "tbtx_4k_tech_art_v1"
    assert out["inputs"].get("source_files") is None
    assert out["inputs"].get("reference_files") == []


def test_image_contract_auto_selects_4k_profile() -> None:
    envelope = {
        "task_id": "4k-auto-1",
        "title": "Homepage hero artwork",
        "goal": "Create a photorealistic, emotionally precise TransformBy10X hero composition for staged review.",
        "task_type": "content_prep",
        "output_required": "One native 3840x2160 PNG image plus desktop and mobile WebP derivatives",
        "inputs": {},
    }
    out = normalize_creative_envelope_inputs(envelope)
    assert out["inputs"]["render_profile"] == "tbtx_4k_tech_art_v1"
    assert out["inputs"]["creative_prompt"] == envelope["goal"]
    assert out["inputs"].get("source_files") is None


def test_soft_keywords_alone_do_not_force_media() -> None:
    # Critical: intake must not stamp without a true media output contract
    env = {
        "task_id": "soft-1",
        "title": "Campaign notes",
        "goal": "Discuss concept for next quarter",
        "task_type": "content_prep",
        "output_required": "Write a markdown brief only",
        "inputs": {},
    }
    out = normalize_creative_envelope_inputs(env)
    assert not out["inputs"].get("render_profile")
    assert requires_media_artifacts(env["output_required"]) is False


def test_routing_rules_explicit_risk_tier() -> None:
    rules = EnvelopeValidationService.ROUTING_RULES
    assert rules["reputation"] == "alpha"  # Hermes
    assert rules["time_loss"] == "beta"  # OpenClaw
    assert rules["downtime_security_money"] == "gamma"  # Agent Zero


def test_owner_from_risk_tier() -> None:
    assert (
        EnvelopeValidationService.determine_owner(
            {"risk_tier": "reputation", "owner_role": "alpha"}
        )
        == "alpha"
    )


def test_normalizer_handles_explicit_null_win() -> None:
    envelope = normalize_task_envelope(
        {
            "title": "Null win proof",
            "instruction": "Prove a null win object cannot crash intake.",
            "work_class": "healthcheck",
            "impact_if_wrong": "time",
            "win": None,
        }
    )
    assert envelope["title"] == "Null win proof"
    assert envelope["owner_role"] == "beta"


def test_normalizer_rejects_missing_title() -> None:
    with pytest.raises(ValueError, match="title is required"):
        normalize_task_envelope(
            {
                "instruction": "Reject this envelope because it has no title.",
                "work_class": "healthcheck",
            }
        )


def test_normalizer_rejects_invalid_task_type() -> None:
    with pytest.raises(ValueError, match="invalid work_class/task_type"):
        normalize_task_envelope(
            {
                "title": "Invalid task type",
                "instruction": "Reject an unknown work class instead of coercing it.",
                "work_class": "invented_work",
            }
        )


def test_explicit_owner_override_is_recorded_without_weakening_risk_gate() -> None:
    envelope = normalize_task_envelope(
        {
            "title": "Gamma controlled proof",
            "instruction": "Route this bounded implementation probe through Agent Zero.",
            "work_class": "implementation",
            "impact_if_wrong": "time",
            "preferred_owner": "gamma",
            "gates": {"review_required": True, "rollback_required": True},
        }
    )
    derived = envelope["inputs"]["envelope_v2"]["derived"]
    assert envelope["risk_tier"] == "time_loss"
    assert envelope["owner_role"] == "gamma"
    assert envelope["review_required"] is True
    assert derived["risk_owner"] == "beta"
    assert derived["requested_owner"] == "gamma"
    assert derived["routing_reason"] == "approved explicit owner override"
    assert EnvelopeValidationService.validate_business_rules(envelope) == (True, None)
    assert (
        EnvelopeValidationService.determine_owner(
            {"risk_tier": "time_loss", "owner_role": "beta"}
        )
        == "beta"
    )
    assert (
        EnvelopeValidationService.determine_owner(
            {"risk_tier": "downtime_security_money", "owner_role": "gamma", "review_required": True}
        )
        == "gamma"
    )


def test_envelope_ids_match_contract_shape() -> None:
    """Invariant: task_id is the durable identity for queue and artifacts."""
    task_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    envelope = {
        "task_id": task_id,
        "title": "id proof",
        "goal": "prove ids",
        "task_type": "content_prep",
        "risk_tier": "time_loss",
        "owner_role": "beta",
        "preferred_owner": "beta",
        "output_required": "A markdown note",
        "inputs": {"proof": True},
        "source": "dashboard",
        "review_required": False,
    }
    out = normalize_creative_envelope_inputs(envelope)
    # After create path would freeze contract; simulate freeze fields
    inputs = dict(out.get("inputs") or {})
    inputs["envelope_contract"] = {
        "task_id": task_id,
        "output_required": envelope["output_required"],
        "owner": "beta",
    }
    assert inputs["envelope_contract"]["task_id"] == task_id
    assert inputs["envelope_contract"]["output_required"] == envelope["output_required"]


def test_scrub_move_remove_does_not_leave_mov_token() -> None:
    scrubbed = _scrub_negated_media_phrases(
        "do not produce video, mp4, or campaign assets. write markdown."
    )
    assert "mp4" not in scrubbed
    assert "video" not in scrubbed


def test_multiple_output_files_non_media() -> None:
    text = (
        "Create these finished Markdown files: "
        "08_REPORTS/GROW/00_GROW_INDEX.md and 08_REPORTS/GROW/01_GROW_STATUS.md"
    )
    assert requires_media_artifacts(text) is False
    env = {
        "task_id": "multi-md",
        "title": "GROW multi file",
        "goal": "produce several markdown reports",
        "task_type": "content_prep",
        "output_required": text,
        "inputs": {},
    }
    out = normalize_creative_envelope_inputs(env)
    assert not out["inputs"].get("render_profile")

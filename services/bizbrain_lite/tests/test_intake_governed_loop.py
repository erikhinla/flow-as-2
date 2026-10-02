"""Prove diagnostic and webhook intake enter the governed loop.

Envelope validation, Redis enqueue, worker acknowledgment, and reflection
write run in-process. The test does not start the VPS compose stack.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "shared"))

from app.services.envelope_validation_service import EnvelopeValidationService  # noqa: E402
from app.services.redis_queue_service import RedisQueueService  # noqa: E402
from intake_envelope import (  # noqa: E402
    build_diagnostic_task_envelope,
    build_intake_reflection,
    build_webhook_task_envelope,
    commit_intake_record,
)


class _FakeRedis:
    """Just enough of redis-py for lpush + brpop FIFO."""

    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}

    async def lpush(self, key: str, value: str) -> int:
        bucket = self.lists.setdefault(key, [])
        bucket.insert(0, value)
        return len(bucket)

    async def llen(self, key: str) -> int:
        return len(self.lists.get(key) or [])

    async def brpop(self, key: str, timeout: int = 0):
        bucket = self.lists.get(key) or []
        if not bucket:
            return None
        value = bucket.pop()
        return (key, value)


def _diagnostic_record() -> dict:
    return {
        "session_id": "DIAG-abc123",
        "lead": {"name": "Ada", "email": "ada@example.com", "company": "Analytical Engines"},
        "diagnostic_type": "tbtx",
        "score": 18,
        "max_score": 40,
        "category": "Infrastructure conversation",
        "route_to": "bizbuilders.ai/roadmap",
    }


def _webhook_submission() -> dict:
    return {
        "name": "Ada",
        "email": "ada@example.com",
        "company": "Analytical Engines",
        "source": "bizbuilders.ai/intake",
        "routing": "Targeted resource",
        "total_gaps": 2,
    }


@pytest.mark.parametrize(
    "builder,payload,source",
    [
        (build_diagnostic_task_envelope, _diagnostic_record(), "landing_page"),
        (build_webhook_task_envelope, _webhook_submission(), "webhook"),
    ],
)
def test_intake_envelope_is_governed(builder, payload, source) -> None:
    envelope = builder(payload)
    schema_ok, schema_error = EnvelopeValidationService.validate_schema(envelope)
    assert schema_ok, schema_error
    rules_ok, rules_error = EnvelopeValidationService.validate_business_rules(envelope)
    assert rules_ok, rules_error

    owner = EnvelopeValidationService.determine_owner(envelope)
    assert envelope["source"] == source
    assert owner == "alpha"
    assert envelope["owner_role"] == owner
    assert envelope["source"] != owner
    assert envelope["task_type"] == "classification"
    assert envelope["risk_tier"] == "reputation"
    assert envelope["status"] == "pending"


def test_null_win_still_normalizes() -> None:
    from app.services.task_envelope_v2 import normalize_task_envelope

    envelope = build_diagnostic_task_envelope(_diagnostic_record())
    envelope["win"] = None
    envelope["output"] = None
    normalized = normalize_task_envelope(envelope)
    assert normalized["risk_tier"] == "reputation"
    assert normalized["owner_role"] == "alpha"
    assert "Analytical Engines" in normalized["title"] or "Ada" in normalized["title"]


def test_envelope_queue_ack_and_reflection() -> None:
    async def _run() -> None:
        envelope = build_diagnostic_task_envelope(_diagnostic_record())
        schema_ok, schema_error = EnvelopeValidationService.validate_schema(envelope)
        assert schema_ok, schema_error
        rules_ok, rules_error = EnvelopeValidationService.validate_business_rules(envelope)
        assert rules_ok, rules_error

        owner = EnvelopeValidationService.determine_owner(envelope)
        queue = RedisQueueService(_FakeRedis())
        assert await queue.enqueue_job(owner, envelope["task_id"]) is True
        assert await queue.get_queue_depth(owner) == 1

        job_id = await queue.dequeue_job(owner, timeout=0)
        assert job_id == envelope["task_id"]
        assert await queue.get_queue_depth(owner) == 0

        reflection = build_intake_reflection(envelope, owner=owner, job_id=job_id)
        assert reflection["task_id"] == envelope["task_id"]
        assert reflection["job_id"] == job_id
        assert reflection["owner"] == "alpha"
        assert reflection["source"] == "landing_page"
        assert reflection["source"] != reflection["owner"]
        assert reflection["status"] == "active"
        assert reflection["skills_used"] == []
        assert reflection["skill_helped"] is False
        assert len(reflection["what_worked"]) >= 10
        assert len(reflection["what_failed"]) >= 10
        assert reflection["tool_sequence"] == ["schema_validate", "enqueue", "worker_ack"]

    asyncio.run(_run())


class _Response:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_commit_writes_mirror_only_after_registry_accepts(tmp_path: Path) -> None:
    envelope = build_webhook_task_envelope(_webhook_submission())
    record = {"intake_ref": "INTAKE-1", "routing": "Targeted resource"}

    def opener(request, timeout):
        assert request.get_header("X-api-token") or request.get_header("X-Api-Token")
        body = json.loads(request.data.decode("utf-8"))
        assert body["task_id"] == envelope["task_id"]
        assert body["source"] == "webhook"
        assert body["owner_role"] == "alpha"
        return _Response(
            {
                "status": "accepted",
                "job_id": envelope["task_id"],
                "owner": "alpha",
                "queue": "flow:alpha:jobs",
            }
        )

    stored, registry = commit_intake_record(
        tmp_path,
        record,
        envelope,
        url="http://bizbrain-lite:8000/v1/intake/task",
        token="test-token",
        opener=opener,
    )
    mirror = tmp_path / f"{envelope['task_id']}.json"
    assert mirror.exists()
    assert stored["job_id"] == registry["job_id"]
    assert stored["owner"] == "alpha"
    assert stored["source"] == "webhook"
    assert json.loads(mirror.read_text())["queue"] == "flow:alpha:jobs"


def test_commit_does_not_write_when_registry_rejects(tmp_path: Path) -> None:
    envelope = build_diagnostic_task_envelope(_diagnostic_record())

    def opener(request, timeout):
        return _Response({"status": "rejected", "error": "schema validation failed"})

    with pytest.raises(RuntimeError, match="schema validation failed"):
        commit_intake_record(
            tmp_path,
            {"session_id": "DIAG-abc123"},
            envelope,
            url="http://bizbrain-lite:8000/v1/intake/task",
            token="test-token",
            opener=opener,
        )
    assert list(tmp_path.glob("*.json")) == []


def test_commit_fails_closed_without_token(tmp_path: Path) -> None:
    envelope = build_webhook_task_envelope(_webhook_submission())
    with pytest.raises(RuntimeError, match="BIZBRAIN_API_TOKEN"):
        commit_intake_record(
            tmp_path,
            {},
            envelope,
            url="http://bizbrain-lite:8000/v1/intake/task",
            token="",
            opener=lambda request, timeout: None,
        )
    assert list(tmp_path.glob("*.json")) == []

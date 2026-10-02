"""Build governed task envelopes for diagnostic and webhook intake.

Flat JSON on disk is a mirror written only after the control plane accepts
the envelope. Source is where the task entered. Owner is who executes it.
"""

from __future__ import annotations

import json
import pathlib
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable


LOCKED_STATUSES = {
    "pending",
    "validated",
    "queued",
    "active",
    "review_required",
    "completed",
    "failed",
    "dead_letter",
    "blocked",
    "escalated",
    "archived",
}

# Reputation-tier classification stays with Alpha. Source stays the entry surface.
INTAKE_RISK_TIER = "reputation"
INTAKE_OWNER = "alpha"
INTAKE_TASK_TYPE = "classification"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_task_id() -> str:
    return str(uuid.uuid4())


def _envelope(
    *,
    task_id: str,
    source: str,
    title: str,
    goal: str,
    notes: str,
    context_refs: list[str],
    extra_inputs: dict[str, Any],
) -> dict[str, Any]:
    if source == INTAKE_OWNER:
        raise ValueError("source and owner must be distinct")
    envelope = {
        "task_id": task_id,
        "created_at": utc_now(),
        "source": source,
        "title": title,
        "goal": goal,
        "task_type": INTAKE_TASK_TYPE,
        "risk_tier": INTAKE_RISK_TIER,
        "preferred_owner": INTAKE_OWNER,
        "owner_role": INTAKE_OWNER,
        "inputs": {
            "notes": notes,
            "context_refs": context_refs,
            **extra_inputs,
        },
        "output_required": (
            "One governed classification record with owner alpha, "
            "distinct from the intake source, and a written reflection."
        ),
        "review_required": False,
        "rollback_required": False,
        "status": "pending",
    }
    if envelope["status"] not in LOCKED_STATUSES:
        raise ValueError(f"status {envelope['status']} is not in the locked status model")
    return envelope


def build_webhook_task_envelope(submission: dict[str, Any], task_id: str | None = None) -> dict[str, Any]:
    """Envelope for POST /intake. Source is the webhook, owner is alpha."""
    origin = str(submission.get("source") or "webhook")
    routing = str(submission.get("routing") or "unspecified")
    company = str(submission.get("company") or "unknown company")
    return _envelope(
        task_id=task_id or new_task_id(),
        source="webhook",
        title="Classify webhook intake submission",
        goal=(
            f"Classify the webhook intake from {origin} for {company} "
            f"and record routing {routing} under owner alpha."
        ),
        notes="Webhook intake entered the governed registry instead of a shadow file.",
        context_refs=["docs/FLOW_AGENT_OS_SPEC_PATCH_v1.md"],
        extra_inputs={
            "intake_origin": origin,
            "routing": routing,
            "total_gaps": submission.get("total_gaps"),
            "lead": {
                "name": submission.get("name"),
                "email": submission.get("email"),
                "company": submission.get("company"),
            },
        },
    )


def build_diagnostic_task_envelope(record: dict[str, Any], task_id: str | None = None) -> dict[str, Any]:
    """Envelope for POST /diagnostic/submit. Source is the landing page, owner is alpha."""
    diagnostic_type = str(record.get("diagnostic_type") or "tbtx")
    category = str(record.get("category") or "unscored")
    score = record.get("score")
    max_score = record.get("max_score")
    report = record.get("report") if isinstance(record.get("report"), dict) else {}
    lead = record.get("lead") if isinstance(record.get("lead"), dict) else {}
    who = str(lead.get("company") or lead.get("name") or "this client")
    headline = str(report.get("headline") or f"{category} diagnostic for {who}")
    next_move = str(report.get("highest_leverage_next_move") or "Deliver the roadmap.")
    return _envelope(
        task_id=task_id or new_task_id(),
        source="landing_page",
        title=headline[:200],
        goal=f"{report.get('summary') or headline} Next move: {next_move}"[:1000],
        notes="Client diagnostic report is the deliverable. Registry acceptance stores the roadmap.",
        context_refs=["docs/USABLE_FLOW_ASAP.md", "docs/FLOW_AGENT_OS_SPEC_PATCH_v1.md"],
        extra_inputs={
            "session_id": record.get("session_id"),
            "diagnostic_type": diagnostic_type,
            "category": category,
            "score": score,
            "max_score": max_score,
            "route_to": record.get("route_to"),
            "lead": lead,
            "client_result": {
                "headline": headline,
                "summary": report.get("summary"),
                "top_gaps": report.get("top_gaps") or [],
                "phased_plan": report.get("phased_plan") or [],
                "highest_leverage_next_move": next_move,
                "next_cta": record.get("next_cta"),
            },
        },
    )


def build_intake_reflection(envelope: dict[str, Any], *, owner: str, job_id: str) -> dict[str, Any]:
    """Reflection written after the worker acknowledges the queued job."""
    if envelope.get("source") == owner:
        raise ValueError("reflection source and owner must stay distinct")
    return {
        "reflection_id": str(uuid.uuid4()),
        "task_id": envelope["task_id"],
        "job_id": job_id,
        "owner": owner,
        "source": envelope["source"],
        "what_worked": (
            "Validated envelope was queued and acknowledged with one owner "
            "and a source that records where it entered."
        ),
        "what_failed": "No execution failure on the intake acknowledgment path.",
        "pattern_observed": "Intake submissions become one governed classification task.",
        "context_type": "intake_form",
        "tool_sequence": ["schema_validate", "enqueue", "worker_ack"],
        "success_signal": "worker acknowledged the queued job_id",
        "failure_signal": "registry rejected the envelope or the queue was empty",
        "sensitivity_level": "internal",
        "created_at": utc_now(),
        "skills_used": [],
        "skill_helped": False,
        "status": "active",
    }


def post_governed_envelope(
    envelope: dict[str, Any],
    *,
    url: str,
    token: str,
    opener: Callable[..., Any],
    timeout: float = 10,
) -> dict[str, Any]:
    """POST a validated envelope to the control-plane intake registry."""
    if not str(token or "").strip():
        raise RuntimeError("BIZBRAIN_API_TOKEN is not set; intake cannot register a governed task")
    if not str(url or "").strip():
        raise RuntimeError("FLOW_INTAKE_URL is not set; intake cannot register a governed task")

    request = urllib.request.Request(
        url,
        data=json.dumps(envelope).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Api-Token": token,
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"registry rejected intake: {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"registry unavailable: {exc.reason}") from exc

    body = json.loads(raw)
    if body.get("status") != "accepted":
        raise RuntimeError(str(body.get("error") or "registry rejected intake"))
    return body


def commit_intake_record(
    directory: str | pathlib.Path,
    record: dict[str, Any],
    envelope: dict[str, Any],
    *,
    url: str,
    token: str,
    opener: Callable[..., Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Register first. Write the JSON mirror only after the registry accepts."""
    registry = post_governed_envelope(envelope, url=url, token=token, opener=opener)
    stored = dict(record)
    stored["task_id"] = envelope["task_id"]
    stored["source"] = envelope["source"]
    stored["owner"] = registry.get("owner") or envelope["owner_role"]
    stored["queue"] = registry.get("queue")
    stored["job_id"] = registry.get("job_id")
    stored["registry_status"] = registry.get("status")
    stored["envelope_status"] = envelope["status"]
    path = pathlib.Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{envelope['task_id']}.json").write_text(json.dumps(stored, indent=2))
    return stored, registry

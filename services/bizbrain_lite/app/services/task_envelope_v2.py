"""
FAAS Task Envelope v2 — operator form → wire (v1-compatible) normalizer.

Operator fills a small surface. System derives owner/engine, freezes contract fields,
and stores the full v2 payload under inputs.envelope_v2 for workers and audit.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Human work class → persisted task_type (DB/schema enum)
WORK_CLASS_TO_TASK_TYPE = {
    "ops_infra": "implementation",
    "strategy_research": "content_prep",
    "creative_export": "content_prep",
    "content_text": "rewrite",
    "implementation": "implementation",
    # legacy passthrough
    "classification": "classification",
    "rewrite": "rewrite",
    "content_prep": "content_prep",
    "skill_extraction": "skill_extraction",
    "healthcheck": "healthcheck",
}

RISK_TO_OWNER = {
    "reputation": "alpha",
    "time_loss": "beta",
    "downtime_security_money": "gamma",
}

# Plain-language impact labels accepted on intake and mapped to risk_tier
IMPACT_TO_RISK = {
    "reputation": "reputation",
    "public": "reputation",
    "time": "time_loss",
    "time_loss": "time_loss",
    "ops": "time_loss",
    "money": "downtime_security_money",
    "security": "downtime_security_money",
    "downtime": "downtime_security_money",
    "downtime_security_money": "downtime_security_money",
    "high": "downtime_security_money",
}

PRIORITY_MAP = {
    "low": "low",
    "medium": "normal",
    "normal": "normal",
    "high": "high",
    "critical": "urgent",
    "urgent": "urgent",
}

DEFAULT_FORBIDDEN_ACTIONS = [
    "publish",
    "delete",
    "rename_outside_scope",
    "change_routing",
    "mint_asset_ids",
    "declare_final_design",
    "infer_media_render",
    "infer_additional_objectives",
]

WORKER_RULES = [
    "Execute the accepted task only.",
    "Do not reinterpret the task.",
    "Do not infer additional objectives.",
    "Do not infer media generation or render profiles.",
    "Do not change routing or risk_tier.",
    "Do not publish unless publish_allowed is true.",
    "Do not modify files outside scope.allowed_paths when that list is non-empty.",
    "Do not treat folder names as final-design approval.",
    "Do not treat provisional working selection as final-design approval.",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []


def is_v2_payload(raw: dict[str, Any]) -> bool:
    if not isinstance(raw, dict):
        return False
    if str(raw.get("schema") or "").startswith("faas.task_envelope"):
        return True
    if str(raw.get("version") or "").startswith("2"):
        return True
    if raw.get("work_class") or raw.get("instruction"):
        return True
    if isinstance(raw.get("scope"), dict) or isinstance(raw.get("creative"), dict):
        return True
    return False


def normalize_task_envelope(raw: dict[str, Any] | None) -> dict[str, Any]:
    """
    Accept v1 wire or v2 operator payload; return v1-compatible envelope for FAAS pipeline.

    Always attaches inputs.envelope_v2 when v2 fields are present.
    """
    if not raw:
        raise ValueError("Empty task envelope")

    data = deepcopy(raw)
    v2_mode = is_v2_payload(data)

    # --- resolve core operator fields ---
    title = str(data.get("title") or "").strip()
    if len(title) < 5:
        raise ValueError("title is required and must be at least 5 characters")
    instruction = str(data.get("instruction") or data.get("goal") or "").strip()
    win = data.get("win") if isinstance(data.get("win"), dict) else {}
    success = data.get("success_looks_like") or win.get("success_condition")
    if isinstance(success, list):
        success_text = "; ".join(str(s).strip() for s in success if str(s).strip())
    else:
        success_text = str(success or "").strip()

    out_of_scope = _as_list(data.get("out_of_scope"))
    if not out_of_scope and isinstance(data.get("win"), dict):
        out_of_scope = _as_list(data["win"].get("out_of_scope"))

    deliverable = str(
        data.get("deliverable")
        or (data.get("output") or {}).get("deliverable")
        or data.get("output_required")
        or ""
    ).strip()

    required_artifacts = _as_list(
        data.get("required_artifacts")
        or (data.get("output") or {}).get("required_artifacts")
    )
    acceptance = _as_list(data.get("acceptance_criteria"))

    # work class / task type
    explicit_work_class = data.get("work_class") or data.get("task_type")
    work_class = str(explicit_work_class or "content_prep").strip()
    if explicit_work_class and work_class not in WORK_CLASS_TO_TASK_TYPE:
        raise ValueError(
            f"invalid work_class/task_type '{work_class}'; "
            f"allowed values: {sorted(WORK_CLASS_TO_TASK_TYPE)}"
        )
    task_type = WORK_CLASS_TO_TASK_TYPE.get(work_class, work_class)

    # risk / owner
    impact = str(data.get("impact_if_wrong") or data.get("risk_tier") or "reputation").strip().lower()
    risk_tier = IMPACT_TO_RISK.get(impact, impact if impact in RISK_TO_OWNER else "reputation")
    risk_owner = RISK_TO_OWNER[risk_tier]
    requested_owner = str(
        data.get("owner_role") or data.get("preferred_owner") or ""
    ).strip()
    if requested_owner and requested_owner not in RISK_TO_OWNER.values():
        raise ValueError(
            f"invalid preferred_owner '{requested_owner}'; allowed values: alpha, beta, gamma"
        )
    owner = requested_owner or risk_owner
    routing_reason = (
        "approved explicit owner override"
        if requested_owner and requested_owner != risk_owner
        else "risk-tier routing"
    )

    priority_raw = str(data.get("priority") or "normal").strip().lower()
    priority = PRIORITY_MAP.get(priority_raw, "normal")

    # scope
    scope_in = data.get("scope") if isinstance(data.get("scope"), dict) else {}
    input_in = data.get("input") if isinstance(data.get("input"), dict) else {}
    inputs_in = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}

    repository = str(
        scope_in.get("repository")
        or input_in.get("repository")
        or inputs_in.get("repository")
        or "~/Documents/TBTX_COMMAND_CENTER"
    ).strip()

    allowed_paths = _as_list(scope_in.get("allowed_paths") or input_in.get("allowed_paths"))
    forbidden_paths = _as_list(scope_in.get("forbidden_paths"))
    working_locations = _as_list(
        scope_in.get("working_locations")
        or input_in.get("working_locations")
        or inputs_in.get("files")
    )
    reference_material = _as_list(
        scope_in.get("reference_material")
        or input_in.get("reference_material")
        or inputs_in.get("context_refs")
    )
    constraints = _as_list(scope_in.get("constraints") or input_in.get("constraints"))

    forbidden_actions = _as_list(scope_in.get("forbidden_actions")) or list(DEFAULT_FORBIDDEN_ACTIONS)
    allowed_actions = _as_list(scope_in.get("allowed_actions")) or [
        "read",
        "write_artifacts",
        "edit_in_scope",
    ]

    # creative
    creative_in = data.get("creative") if isinstance(data.get("creative"), dict) else {}
    if not creative_in and input_in:
        creative_in = {
            "campaign": input_in.get("campaign") or "",
            "project": input_in.get("project") or "",
            "asset_label": input_in.get("asset") or "",
        }
    design_lifecycle = str(
        creative_in.get("design_lifecycle") or "provisional_working"
    ).strip()
    if design_lifecycle not in {
        "provisional_working",
        "provisional_review",
        "final_explicit",
    }:
        design_lifecycle = "provisional_working"
    final_ref = creative_in.get("final_approval_reference")
    if design_lifecycle == "final_explicit" and not final_ref:
        raise ValueError(
            "design_lifecycle=final_explicit requires creative.final_approval_reference"
        )

    # gates
    gates = data.get("gates") if isinstance(data.get("gates"), dict) else {}
    review_required = bool(
        gates.get("review_required")
        if "review_required" in gates
        else data.get("review_required", risk_tier == "downtime_security_money")
    )
    if risk_tier == "downtime_security_money":
        review_required = True
    rollback_required = bool(
        gates.get("rollback_required")
        if "rollback_required" in gates
        else data.get("rollback_required", risk_tier == "downtime_security_money")
    )
    publish_allowed = bool(gates.get("publish_allowed", False))

    reconciliation = data.get("reconciliation") if isinstance(data.get("reconciliation"), dict) else {}

    # goal / output_required for wire + workers
    goal_parts = [instruction]
    if success_text:
        goal_parts.append(f"Success looks like: {success_text}")
    if out_of_scope:
        goal_parts.append("Out of scope: " + "; ".join(out_of_scope))
    if constraints:
        goal_parts.append("Constraints: " + "; ".join(constraints))
    goal = "\n\n".join(p for p in goal_parts if p).strip()
    if len(goal) < 10:
        raise ValueError("instruction/goal must be at least 10 characters")

    output_bits = []
    if deliverable:
        output_bits.append(deliverable)
    if required_artifacts:
        output_bits.append("Required artifacts: " + ", ".join(required_artifacts))
    if acceptance:
        output_bits.append("Acceptance: " + "; ".join(acceptance))
    output_required = "\n".join(output_bits).strip() or deliverable or success_text or instruction
    if len(output_required) < 5:
        output_required = "A finished artifact that satisfies the instruction."

    # ids
    task_id = str(data.get("task_id") or uuid4())
    created_at = str(data.get("created_at") or _utc_now())
    source = str(data.get("source") or "dashboard")

    envelope_v2 = {
        "schema": "faas.task_envelope",
        "version": "2.0",
        "work_class": work_class if work_class in WORK_CLASS_TO_TASK_TYPE else task_type,
        "instruction": instruction or goal,
        "success_looks_like": _as_list(data.get("success_looks_like")) or (
            [success_text] if success_text else []
        ),
        "out_of_scope": out_of_scope,
        "deliverable": deliverable,
        "required_artifacts": required_artifacts,
        "acceptance_criteria": acceptance,
        "priority": priority,
        "scope": {
            "repository": repository,
            "allowed_paths": allowed_paths,
            "forbidden_paths": forbidden_paths,
            "allowed_actions": allowed_actions,
            "forbidden_actions": forbidden_actions,
            "working_locations": working_locations,
            "reference_material": reference_material,
            "constraints": constraints,
        },
        "creative": {
            "campaign": str(creative_in.get("campaign") or ""),
            "project": str(creative_in.get("project") or ""),
            "asset_label": str(
                creative_in.get("asset_label") or creative_in.get("asset") or ""
            ),
            "permanent_asset_id": creative_in.get("permanent_asset_id"),
            "design_lifecycle": design_lifecycle,
            "final_approval_reference": final_ref,
            "defined_use": str(creative_in.get("defined_use") or ""),
        },
        "gates": {
            "review_required": review_required,
            "rollback_required": rollback_required,
            "publish_allowed": publish_allowed,
        },
        "reconciliation": reconciliation or None,
        "execution_contract": {
            "immutable_after_acceptance": [
                "risk_tier",
                "work_class",
                "instruction",
                "required_artifacts",
                "acceptance_criteria",
                "scope.allowed_paths",
                "scope.forbidden_actions",
                "creative.design_lifecycle",
            ],
            "worker_rules": list(WORKER_RULES),
        },
        "completion": {
            "required_returns": ["summary", "artifacts_created", "files_changed", "proof"],
            "completion_standard": (
                "Complete only when every required artifact exists, every acceptance "
                "criterion passes, and proof is available through the FAAS dashboard."
            ),
        },
        "derived": {
            "task_type": task_type,
            "risk_tier": risk_tier,
            "requested_owner": requested_owner or None,
            "risk_owner": risk_owner,
            "owner_role": owner,
            "routing_reason": routing_reason,
            "engine": {"alpha": "hermes", "beta": "openclaw", "gamma": "agent_zero"}[owner],
        },
    }

    # Preserve prior inputs keys and attach v2
    inputs: dict[str, Any] = dict(inputs_in)
    if working_locations and not inputs.get("files"):
        inputs["files"] = working_locations
    if reference_material and not inputs.get("context_refs"):
        inputs["context_refs"] = reference_material
    if v2_mode or data.get("instruction") or data.get("work_class"):
        inputs["envelope_v2"] = envelope_v2
        inputs["work_class"] = envelope_v2["work_class"]
        inputs["design_lifecycle"] = design_lifecycle
        inputs["publish_allowed"] = publish_allowed
        inputs["forbidden_actions"] = forbidden_actions
        inputs["acceptance_criteria"] = acceptance
        inputs["required_artifacts"] = required_artifacts

    wire = {
        "task_id": task_id,
        "created_at": created_at,
        "source": source,
        "title": title,
        "goal": goal,
        "task_type": task_type,
        "risk_tier": risk_tier,
        "priority": priority,
        "preferred_owner": owner,
        "owner_role": owner,
        "inputs": inputs,
        "output_required": output_required,
        "review_required": review_required,
        "rollback_required": rollback_required,
        "status": str(data.get("status") or "pending"),
    }

    return wire

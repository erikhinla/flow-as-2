"""Deterministic task-to-model policy for FAAS agent runs.

The router makes one decision before an official agent starts. Runtime adapters
must use this exact model or fail; they may not silently substitute another
model or bypass the assigned agent with a plain chat-completions call.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MODEL_PROFILES = {
    "fast": "openai/gpt-5.6-luna",
    "balanced": "openai/gpt-5.6-terra",
    "creative": "anthropic/claude-sonnet-5",
    "deep": "openai/gpt-5.6-sol",
}

ALLOWED_MODELS = frozenset(MODEL_PROFILES.values())


@dataclass(frozen=True)
class ModelDecision:
    profile: str
    model: str
    reason: str
    hermes_toolsets: tuple[str, ...] = ()
    hermes_skills: tuple[str, ...] = ()
    openclaw_thinking: str = "high"

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["hermes_toolsets"] = list(self.hermes_toolsets)
        value["hermes_skills"] = list(self.hermes_skills)
        return value


def _profile_for_task(task_type: str, risk_tier: str) -> tuple[str, str]:
    if task_type in {"healthcheck", "classification"}:
        return "fast", "bounded verification or classification"
    if task_type == "skill_extraction":
        return "balanced", "structured extraction with moderate reasoning"
    if task_type == "rewrite":
        return "creative", "language quality and instruction fidelity"
    if task_type == "content_prep":
        if risk_tier == "reputation":
            return "deep", "high-stakes public brand or creative work"
        return "creative", "content development and creative judgment"
    if task_type == "implementation":
        if risk_tier == "downtime_security_money":
            return "deep", "high-impact implementation"
        return "balanced", "standard implementation"
    return "balanced", "unclassified work uses the balanced model"


def _hermes_capabilities(task_type: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if task_type in {"content_prep", "rewrite"}:
        return (
            (
                "web",
                "browser",
                "terminal",
                "file",
                "code_execution",
                "vision",
                "image_gen",
                "skills",
                "todo",
                "memory",
                "session_search",
            ),
            (
                "faas-brand-campaign-producer",
                "humanizer",
                "design-md",
                "popular-web-designs",
                "claude-design",
            ),
        )
    if task_type == "implementation":
        return (
            ("web", "terminal", "file", "code_execution", "skills", "todo", "memory"),
            ("test-driven-development", "systematic-debugging", "requesting-code-review"),
        )
    if task_type == "skill_extraction":
        return (("file", "skills", "memory"), ("hermes-agent-skill-authoring",))
    return (("file", "skills"), ())


def select_model(
    *,
    task_type: str,
    risk_tier: str,
    inputs: dict[str, Any] | None = None,
) -> ModelDecision:
    """Return the single model decision that every runtime must honor."""
    normalized_task = str(task_type or "content_prep").strip().lower()
    normalized_risk = str(risk_tier or "time_loss").strip().lower()
    supplied = inputs if isinstance(inputs, dict) else {}

    requested_model = str(supplied.get("model_override") or "").strip()
    requested_profile = str(supplied.get("model_profile") or "").strip().lower()
    if requested_model:
        if requested_model not in ALLOWED_MODELS:
            raise ValueError(
                f"model_override '{requested_model}' is not approved; "
                f"allowed models: {sorted(ALLOWED_MODELS)}"
            )
        profile = next(
            (name for name, model in MODEL_PROFILES.items() if model == requested_model),
            "explicit",
        )
        reason = "approved explicit model override"
    elif requested_profile:
        if requested_profile not in MODEL_PROFILES:
            raise ValueError(
                f"model_profile '{requested_profile}' is not approved; "
                f"allowed profiles: {sorted(MODEL_PROFILES)}"
            )
        profile = requested_profile
        requested_model = MODEL_PROFILES[profile]
        reason = "approved explicit model profile"
    else:
        profile, reason = _profile_for_task(normalized_task, normalized_risk)
        requested_model = MODEL_PROFILES[profile]

    toolsets, skills = _hermes_capabilities(normalized_task)
    return ModelDecision(
        profile=profile,
        model=requested_model,
        reason=reason,
        hermes_toolsets=toolsets,
        hermes_skills=skills,
        openclaw_thinking="off" if profile == "fast" else "high",
    )

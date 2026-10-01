"""Client diagnostic reports written by the intake webhook."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends

from app.api.deps import require_api_token

router = APIRouter(
    prefix="/client-diagnostics",
    tags=["client-diagnostics"],
    dependencies=[Depends(require_api_token)],
)


def results_dir() -> Path:
    return Path(os.getenv("INTAKE_RESULTS_DIR", "/workspace/runtime/intake"))


def _lead(record: dict) -> dict:
    lead = record.get("lead")
    return lead if isinstance(lead, dict) else {}


def _report(record: dict) -> dict:
    report = record.get("report")
    return report if isinstance(report, dict) else {}


@router.get("")
def list_client_diagnostics() -> dict:
    directory = results_dir()
    if not directory.is_dir():
        return {"results": []}

    results = []
    files = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files[:30]:
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict) or "report" not in record:
            continue
        lead = _lead(record)
        report = _report(record)
        results.append(
            {
                "session_id": record.get("session_id"),
                "task_id": record.get("task_id"),
                "name": lead.get("name") or "",
                "company": lead.get("company") or "",
                "role": lead.get("role") or "",
                "industry": lead.get("industry") or "",
                "category": record.get("category") or "",
                "score": record.get("score"),
                "max_score": record.get("max_score"),
                "headline": report.get("headline") or "",
                "summary": report.get("summary") or "",
                "industry_context": report.get("industry_context") or "",
                "top_gaps": report.get("top_gaps") or [],
                "recommended_infrastructure": report.get("recommended_infrastructure") or [],
                "phased_plan": report.get("phased_plan") or [],
                "next_move": report.get("highest_leverage_next_move") or "",
                "next_cta": record.get("next_cta") or "",
                "route_to": record.get("route_to") or "",
                "owner": record.get("owner") or "",
                "created": record.get("created") or "",
            }
        )
    return {"results": results}

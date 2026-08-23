"""Activepieces-to-Postiz social handoff with Redis-backed idempotency."""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis

from app.api.deps import require_api_token
from app.api.openclaw_intake import get_redis_queue_service
from app.config.settings import get_settings
from app.services.postiz_client import PostizClient, PostizConfigurationError, build_postiz_payload

router = APIRouter(prefix="/social", tags=["social"], dependencies=[Depends(require_api_token)])
IDEMPOTENCY_TTL_SECONDS = 7 * 24 * 60 * 60


class SocialPostRequest(BaseModel):
    """The final, account-specific handoff produced by Activepieces."""

    idempotency_key: str = Field(min_length=8, max_length=200)
    account: Literal["erikhbush", "transformby10x"]
    platform: Literal["x", "linkedin", "linkedin-page", "instagram", "facebook", "threads", "bluesky"]
    content: str = Field(min_length=1, max_length=100_000)
    mode: Literal["draft", "schedule", "now"] = "draft"
    scheduled_at: str | None = None
    media: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[dict[str, Any]] = Field(default_factory=list)
    short_link: bool = False
    instagram_post_type: Literal["post", "reel", "story"] | None = None

    @field_validator("scheduled_at")
    @classmethod
    def scheduled_posts_need_time(cls, value: str | None, info):
        if info.data.get("mode") == "schedule" and not value:
            raise ValueError("scheduled_at is required when mode is schedule")
        return value


def _integration_id(account: str, platform: str) -> str:
    settings = get_settings()
    try:
        configured = json.loads(settings.postiz_integration_map or "{}")
        integration_id = str((configured.get(account) or {}).get(platform) or "").strip()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail="POSTIZ_INTEGRATION_MAP is not valid JSON") from exc
    if not integration_id:
        raise HTTPException(
            status_code=503,
            detail=f"No Postiz integration configured for {account}/{platform}",
        )
    return integration_id


@router.post("/postiz")
async def send_to_postiz(
    request: SocialPostRequest,
    queue_service=Depends(get_redis_queue_service),
) -> dict[str, Any]:
    """Create a Postiz draft, schedule, or immediate post exactly once per key."""
    redis: Redis = queue_service.redis
    key = f"flow:social:idempotency:{request.idempotency_key}"
    result_key = f"{key}:result"
    acquired = await redis.set(key, b"processing", ex=IDEMPOTENCY_TTL_SECONDS, nx=True)
    if not acquired:
        previous = await redis.get(result_key)
        if previous:
            return {"idempotent_replay": True, **json.loads(previous)}
        raise HTTPException(status_code=409, detail="This social handoff is already processing")

    try:
        payload = build_postiz_payload(
            mode=request.mode,
            date=request.scheduled_at,
            integration_id=_integration_id(request.account, request.platform),
            platform=request.platform,
            content=request.content,
            media=request.media,
            tags=request.tags,
            short_link=request.short_link,
            post_type=request.instagram_post_type,
        )
        settings = get_settings()
        postiz = PostizClient(settings.postiz_api_base_url, settings.postiz_api_key)
        response = await postiz.create_post(payload)
        result = {
            "accepted": True,
            "account": request.account,
            "platform": request.platform,
            "mode": request.mode,
            "postiz": response,
        }
        await redis.set(result_key, json.dumps(result), ex=IDEMPOTENCY_TTL_SECONDS)
        return result
    except (ValueError, PostizConfigurationError) as exc:
        await redis.delete(key)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await redis.delete(key)
        raise HTTPException(status_code=502, detail=f"Postiz handoff failed: {exc}") from exc

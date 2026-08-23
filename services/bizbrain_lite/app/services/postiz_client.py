"""Small, explicit client for the Postiz public API."""

from __future__ import annotations

from typing import Any

import httpx


class PostizConfigurationError(RuntimeError):
    """Raised when the social handoff is missing a required Postiz setting."""


def postiz_settings(platform: str, post_type: str | None = None) -> dict[str, Any]:
    settings: dict[str, Any] = {"__type": platform}
    if platform == "instagram":
        settings["post_type"] = post_type or "post"
    return settings


def build_postiz_payload(
    *,
    mode: str,
    date: str | None,
    integration_id: str,
    platform: str,
    content: str,
    media: list[dict[str, Any]],
    tags: list[dict[str, Any]],
    short_link: bool,
    post_type: str | None = None,
) -> dict[str, Any]:
    """Build the documented Postiz POST /posts payload without sending it."""
    if mode not in {"draft", "schedule", "now"}:
        raise ValueError("mode must be draft, schedule, or now")
    if mode == "schedule" and not date:
        raise ValueError("scheduled posts require date")
    if not integration_id:
        raise ValueError("Postiz integration id is required")
    if not content.strip():
        raise ValueError("post content is required")
    return {
        "type": mode,
        "date": date,
        "shortLink": short_link,
        "tags": tags,
        "posts": [
            {
                "integration": {"id": integration_id},
                "value": [{"content": content, "image": media}],
                "settings": postiz_settings(platform, post_type),
            }
        ],
    }


class PostizClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 30.0):
        if not base_url.strip() or not api_key.strip():
            raise PostizConfigurationError(
                "POSTIZ_API_BASE_URL and POSTIZ_API_KEY must be configured"
            )
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def create_post(self, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/posts",
                headers={"Authorization": self.api_key, "Content-Type": "application/json"},
                json=payload,
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Postiz POST /posts HTTP {response.status_code}: {response.text[:500]}")
        return response.json()

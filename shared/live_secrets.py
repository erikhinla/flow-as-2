"""Placeholder-secret checks for a live FLOW deploy.

The host deploy script runs this file directly. The control plane imports
assert_production_token so a production process will not boot on a default token.
"""

from __future__ import annotations

import os
import sys

PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        "change-me",
        "change-me-dashboard-password",
        "replace_with_long_random_token",
        "replace_with_same_value_as_bizbrain_api_token_unless_rotated",
        "replace_with_strong_password",
        "replace_with_dashboard_password",
        "replace_with_webhook_secret",
        "password",
        "admin",
    }
)

# Reject characters that break the Postgres URL or the nginx token header.
_UNSAFE_TOKEN_CHARS = set("\"'\n\r\t $`@:/?#&")


def secret_is_live(value: str, *, minimum: int = 24) -> bool:
    text = (value or "").strip()
    if text in PLACEHOLDER_SECRETS or len(text) < minimum:
        return False
    if any(char in text for char in _UNSAFE_TOKEN_CHARS):
        return False
    return True


def assert_production_token(env: str, token: str) -> None:
    if (env or "").lower() not in {"prod", "production"}:
        return
    if not secret_is_live(token):
        raise RuntimeError("Refusing to start: BIZBRAIN_API_TOKEN is not a production secret")


def main() -> int:
    names = (
        "BIZBRAIN_API_TOKEN",
        "FLOW_DB_PASSWORD",
        "DASHBOARD_BASIC_AUTH_PASSWORD",
        "WEBHOOK_API_KEY",
    )
    missing = [name for name in names if not secret_is_live(os.environ.get(name, ""))]
    hosts = (os.environ.get("DIAGNOSTIC_HOST", "").strip(), os.environ.get("DESK_HOST", "").strip())
    external_proxy = os.environ.get("EXTERNAL_PROXY", "").strip() == "1"
    if any(hosts) and not external_proxy and (not all(hosts) or not os.environ.get("ACME_EMAIL", "").strip()):
        missing.append("DIAGNOSTIC_HOST, DESK_HOST, and ACME_EMAIL")
    if missing:
        print(
            "Live environment is missing production secrets: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

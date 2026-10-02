"""Production boot must refuse placeholder API tokens."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "shared"))

from live_secrets import assert_production_token, secret_is_live  # noqa: E402


def test_dev_keeps_the_local_default_token():
    assert_production_token("dev", "change-me")


def test_production_rejects_placeholder_token():
    with pytest.raises(RuntimeError, match="production secret"):
        assert_production_token("prod", "change-me")


def test_production_rejects_short_token():
    with pytest.raises(RuntimeError):
        assert_production_token("production", "a" * 23)


def test_production_rejects_url_breaking_token():
    with pytest.raises(RuntimeError):
        assert_production_token("prod", "flow-live-token-with-at@sign")


def test_production_accepts_a_long_token():
    token = "flow-live-" + ("a" * 24)
    assert secret_is_live(token)
    assert_production_token("prod", token)


def test_host_checker_rejects_placeholders():
    env = os.environ.copy()
    env.update(
        {
            "BIZBRAIN_API_TOKEN": "change-me",
            "FLOW_DB_PASSWORD": "change-me",
            "DASHBOARD_BASIC_AUTH_PASSWORD": "change-me-dashboard-password",
            "WEBHOOK_API_KEY": "replace_with_webhook_secret",
        }
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "shared" / "live_secrets.py")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "BIZBRAIN_API_TOKEN" in result.stderr


def test_host_checker_accepts_live_secrets():
    env = os.environ.copy()
    env.update(
        {
            "BIZBRAIN_API_TOKEN": "flow-live-token-" + ("b" * 16),
            "FLOW_DB_PASSWORD": "flow-live-db-" + ("c" * 16),
            "DASHBOARD_BASIC_AUTH_PASSWORD": "flow-live-desk-" + ("d" * 16),
            "WEBHOOK_API_KEY": "flow-live-hook-" + ("e" * 16),
            "DIAGNOSTIC_HOST": "",
            "DESK_HOST": "",
            "ACME_EMAIL": "",
        }
    )
    result = subprocess.run(
        [sys.executable, str(REPO / "shared" / "live_secrets.py")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

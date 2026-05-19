"""Shared n8n webhook notification helper."""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import requests
from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger(__name__)
N8N_WEBHOOK_URL = "N8N_WEBHOOK_URL"
PAYLOAD_LOG_PATH = Path("logs") / "n8n_payload.json"
RESPONSE_LOG_PATH = Path("logs") / "n8n_response.json"


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _standard_payload(event_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "source": payload.get("source", "unknown"),
        "status": payload.get("status", "unknown"),
        "revenue": payload.get("revenue", 0),
        "message": payload.get("message", ""),
        "occurred_at": payload.get(
            "occurred_at",
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
        ),
        "raw": payload.get("raw", {}),
    }


def _save_payload(payload: Mapping[str, Any]) -> None:
    PAYLOAD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    PAYLOAD_LOG_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )
    LOGGER.info("Saved n8n payload to %s", PAYLOAD_LOG_PATH)


def _save_response(status: str, http_status: int | None = None, body: str = "") -> None:
    RESPONSE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESPONSE_LOG_PATH.write_text(
        json.dumps(
            {
                "status": status,
                "http_status": http_status,
                "body": body[:2000],
                "occurred_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    LOGGER.info("Saved n8n response to %s", RESPONSE_LOG_PATH)


def notify_n8n(event_type: str, payload: Mapping[str, Any], dry_run: bool = False) -> bool:
    """Send a standard JSON event to n8n.

    Returns True when a webhook request was sent successfully. Missing webhook
    configuration, dry-run mode, and delivery failures are logged and skipped so
    callers can continue their primary job.
    """
    body = _standard_payload(event_type, payload)
    _save_payload(body)
    webhook_url = os.getenv(N8N_WEBHOOK_URL)

    if dry_run:
        _save_response("dry-run")
        LOGGER.info(
            "[dry-run] n8n notification: %s",
            json.dumps(body, ensure_ascii=False, default=_json_default),
        )
        return False

    if not webhook_url:
        LOGGER.info("%s is not set; skipping n8n notification", N8N_WEBHOOK_URL)
        _save_response("skipped")
        return False

    try:
        response = requests.post(webhook_url, json=body, timeout=10)
        _save_response("sent", response.status_code, response.text)
        response.raise_for_status()
    except requests.RequestException as exc:
        LOGGER.warning("Failed to send n8n notification: %s", exc)
        return False

    LOGGER.info("Sent n8n notification event_type=%s http_status=%d", event_type, response.status_code)
    return True

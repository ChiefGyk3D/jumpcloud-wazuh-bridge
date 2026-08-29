from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .client import JumpCloudClient

log = logging.getLogger(__name__)

# JumpCloud ingestion latency: events can be indexed late, so poll up to
# now - LAG_BUFFER_SECONDS to avoid permanently skipping late-arriving events.
LAG_BUFFER_SECONDS = 90


def load_cursor(state_file: str) -> datetime | None:
    """Read the last poll end-time from the cursor file."""
    path = Path(state_file)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Corrupt cursor file %s: %s — starting fresh", state_file, exc)
        return None
    value = data.get("last_end_time")
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def save_cursor(state_file: str, end_time: datetime) -> None:
    """Persist the last poll end-time so the next run picks up where we left off."""
    path = Path(state_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(
        json.dumps({"last_end_time": end_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def poll_once(
    client: JumpCloudClient,
    state_file: str,
    lookback_minutes: int,
    services: list[str] | None = None,
    page_limit: int = 1000,
) -> tuple[list[dict[str, Any]], datetime]:
    """Run a single poll cycle and return (events, end_time)."""
    now = datetime.now(timezone.utc)
    end = now - timedelta(seconds=LAG_BUFFER_SECONDS)
    start = load_cursor(state_file) or (now - timedelta(minutes=lookback_minutes))
    if end <= start:
        log.info("Window not yet past lag buffer (start=%s, end=%s) — skipping", start.isoformat(), end.isoformat())
        return [], start
    log.info("Polling JumpCloud events from %s to %s", start.isoformat(), end.isoformat())
    events = client.fetch_events(
        start_time=start,
        end_time=end,
        services=services,
        page_limit=page_limit,
    )
    return events, end

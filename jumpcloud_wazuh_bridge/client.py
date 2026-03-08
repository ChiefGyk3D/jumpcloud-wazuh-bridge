from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import requests

log = logging.getLogger(__name__)

# JumpCloud Directory Insights API docs:
# https://docs.jumpcloud.com/api/insights/directory/1.0/index.html
#
# • Single POST endpoint: /insights/directory/v1/events
# • Required body fields: service (list[str]), start_time (RFC 3339)
# • Pagination: when X-Result-Count == X-Limit, re-issue with search_after
#   from X-Search_after response header.
# • Max page size: 10 000 rows.


class JumpCloudClient:
    """Thin wrapper around the JumpCloud Directory Insights Events API."""

    def __init__(self, base_url: str, api_key: str, org_id: str = "") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        headers: dict[str, str] = {
            "x-api-key": api_key,
            "accept": "application/json",
            "content-type": "application/json",
        }
        if org_id:
            headers["x-org-id"] = org_id
        self.session.headers.update(headers)

    # ------------------------------------------------------------------
    def fetch_events(
        self,
        start_time: datetime,
        end_time: datetime,
        services: list[str] | None = None,
        page_limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Fetch all pages of Directory Insights events between two timestamps."""
        url = f"{self.base_url}/insights/directory/v1/events"
        payload: dict[str, Any] = {
            "service": services or ["all"],
            "start_time": _rfc3339(start_time),
            "end_time": _rfc3339(end_time),
            "sort": "ASC",
            "limit": min(page_limit, 10_000),
        }

        all_events: list[dict[str, Any]] = []
        page = 0

        while True:
            resp = self.session.post(url, json=payload, timeout=30)
            resp.raise_for_status()

            events = resp.json()
            if not isinstance(events, list):
                log.warning("Unexpected response type: %s", type(events))
                break

            all_events.extend(events)
            page += 1

            # Pagination: compare X-Result-Count to X-Limit
            result_count = int(resp.headers.get("X-Result-Count", 0))
            limit = int(resp.headers.get("X-Limit", 0))

            if result_count < limit or result_count == 0:
                break  # last page

            search_after_raw = resp.headers.get("X-Search_after", "")
            if not search_after_raw:
                break

            try:
                payload["search_after"] = json.loads(search_after_raw)
            except json.JSONDecodeError:
                log.warning("Could not parse X-Search_after header: %s", search_after_raw)
                break

            log.info("Page %d fetched (%d events), continuing…", page, result_count)

        log.info("Total events fetched: %d across %d page(s)", len(all_events), page)
        return all_events

    # Backwards-compatible alias
    fetch_directory_insights = fetch_events


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

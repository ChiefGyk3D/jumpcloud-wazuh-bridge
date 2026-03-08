from dataclasses import dataclass
import json
import logging
import os
import subprocess

import requests as _requests

log = logging.getLogger(__name__)


def _doppler_secrets() -> dict[str, str]:
    """Load secrets from Doppler.

    Resolution order:
      1. DOPPLER_TOKEN env var → Doppler HTTP API (no CLI needed)
      2. Doppler CLI (if installed and logged in, or DOPPLER_TOKEN is set)
      3. Empty dict → fall back to plain environment variables

    On the SIEM server, set DOPPLER_TOKEN to a service token scoped to
    siem-pfsense/prd.  No `doppler login` or CLI install required.
    """
    # --- Method 1: direct HTTP with a service token (no CLI needed) ---
    token = os.environ.get("DOPPLER_TOKEN", "")
    if token:
        try:
            resp = _requests.get(
                "https://api.doppler.com/v3/configs/config/secrets/download",
                params={"format": "json"},
                auth=(token, ""),
                timeout=10,
            )
            if resp.status_code == 200:
                log.info("Secrets loaded from Doppler API (service token)")
                return resp.json()
            log.warning("Doppler API returned %d", resp.status_code)
        except Exception as exc:
            log.warning("Doppler API call failed: %s", exc)

    # --- Method 2: Doppler CLI (dev workstations with `doppler login`) ---
    try:
        result = subprocess.run(
            ["doppler", "secrets", "download", "--no-file", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            log.info("Secrets loaded from Doppler CLI")
            return json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    return {}


def _get(key: str, default: str = "", doppler: dict[str, str] | None = None) -> str:
    """Resolve a config value: Doppler → env var → default."""
    if doppler and key in doppler:
        return doppler[key]
    return os.environ.get(key, default)


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    org_id: str
    lookback_minutes: int
    poll_seconds: int
    output_file: str
    state_file: str
    services: list[str]
    page_limit: int


def load_settings() -> Settings:
    doppler = _doppler_secrets()
    return Settings(
        api_key=_get("JUMPCLOUD_API_KEY", "", doppler),
        base_url=_get("JUMPCLOUD_BASE_URL", "https://api.jumpcloud.com", doppler),
        org_id=_get("JUMPCLOUD_ORG_ID", "", doppler),
        lookback_minutes=int(_get("JUMPCLOUD_LOOKBACK_MINUTES", "15", doppler)),
        poll_seconds=int(_get("JUMPCLOUD_POLL_SECONDS", "300", doppler)),
        output_file=_get("JUMPCLOUD_OUTPUT_FILE", "/tmp/jumpcloud-events.jsonl", doppler),
        state_file=_get("JUMPCLOUD_STATE_FILE", "/tmp/jumpcloud-cursor.json", doppler),
        services=_get("JUMPCLOUD_SERVICES", "all", doppler).split(","),
        page_limit=int(_get("JUMPCLOUD_PAGE_LIMIT", "1000", doppler)),
    )

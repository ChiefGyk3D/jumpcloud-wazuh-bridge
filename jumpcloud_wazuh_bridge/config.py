import json
import logging
import os
import subprocess
from dataclasses import dataclass

import requests as _requests

log = logging.getLogger(__name__)

# Service names accepted by the Directory Insights API (see README
# "Event Services" table). Unknown names are not rejected — JumpCloud may
# add services faster than we update this list — but they are warned about.
KNOWN_SERVICES = frozenset(
    {
        "all",
        "directory",
        "sso",
        "radius",
        "ldap",
        "systems",
        "software",
        "mdm",
        "alerts",
        "password_manager",
        "access_management",
        "asset_management",
        "reports",
        "saas_app_management",
        "object_storage",
        "notifications",
    }
)

# Directory Insights caps page size at 10 000 rows.
MAX_PAGE_LIMIT = 10_000


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
        except _requests.RequestException as exc:
            log.warning("Doppler API call failed: %s", exc)

    # --- Method 2: Doppler CLI (dev workstations with `doppler login`) ---
    try:
        result = subprocess.run(
            ["doppler", "secrets", "download", "--no-file", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
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


def _int_setting(name: str, default: str, doppler: dict[str, str] | None) -> int:
    """Parse an integer setting, re-raising parse failures with the variable name."""
    raw = _get(name, default, doppler)
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None


def load_settings() -> Settings:
    doppler = _doppler_secrets()

    poll_seconds = _int_setting("JUMPCLOUD_POLL_SECONDS", "300", doppler)
    if poll_seconds <= 0:
        raise ValueError(
            f"JUMPCLOUD_POLL_SECONDS must be greater than 0, got {poll_seconds}"
        )

    page_limit = _int_setting("JUMPCLOUD_PAGE_LIMIT", "1000", doppler)
    if not 1 <= page_limit <= MAX_PAGE_LIMIT:
        clamped = min(max(page_limit, 1), MAX_PAGE_LIMIT)
        log.warning(
            "JUMPCLOUD_PAGE_LIMIT=%d out of range 1..%d — clamping to %d",
            page_limit,
            MAX_PAGE_LIMIT,
            clamped,
        )
        page_limit = clamped

    services = [
        s.strip()
        for s in _get("JUMPCLOUD_SERVICES", "all", doppler).split(",")
        if s.strip()
    ]
    unknown = [s for s in services if s not in KNOWN_SERVICES]
    if unknown:
        log.warning(
            "Unknown JumpCloud service name(s) %s — known services: %s",
            ", ".join(unknown),
            ", ".join(sorted(KNOWN_SERVICES)),
        )

    return Settings(
        api_key=_get("JUMPCLOUD_API_KEY", "", doppler),
        base_url=_get("JUMPCLOUD_BASE_URL", "https://api.jumpcloud.com", doppler),
        org_id=_get("JUMPCLOUD_ORG_ID", "", doppler),
        lookback_minutes=_int_setting("JUMPCLOUD_LOOKBACK_MINUTES", "15", doppler),
        poll_seconds=poll_seconds,
        output_file=_get("JUMPCLOUD_OUTPUT_FILE", "/tmp/jumpcloud-events.jsonl", doppler),
        state_file=_get("JUMPCLOUD_STATE_FILE", "/tmp/jumpcloud-cursor.json", doppler),
        services=services,
        page_limit=page_limit,
    )

from dataclasses import dataclass
import json
import os
import subprocess


def _doppler_secrets() -> dict[str, str]:
    """Attempt to load secrets from Doppler CLI.

    Returns an empty dict when Doppler is not installed or not configured,
    allowing a graceful fallback to environment variables.
    """
    try:
        result = subprocess.run(
            ["doppler", "secrets", "download", "--no-file", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
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

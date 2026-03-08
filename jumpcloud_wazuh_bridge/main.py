from __future__ import annotations

import argparse
import logging
import time

from .client import JumpCloudClient
from .config import load_settings
from .poller import poll_once, save_cursor
from .writer import append_jsonl

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)


def run_once() -> int:
    settings = load_settings()
    if not settings.api_key:
        raise SystemExit("JUMPCLOUD_API_KEY is required (set via env var or Doppler)")

    client = JumpCloudClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        org_id=settings.org_id,
    )
    events, end_time = poll_once(
        client,
        settings.state_file,
        settings.lookback_minutes,
        services=settings.services,
        page_limit=settings.page_limit,
    )
    written = append_jsonl(settings.output_file, events)
    save_cursor(settings.state_file, end_time)
    log.info("events_written=%d", written)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="JumpCloud -> Wazuh JSONL bridge")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    settings = load_settings()
    log.info(
        "Starting continuous polling (interval=%ds, services=%s, output=%s)",
        settings.poll_seconds,
        settings.services,
        settings.output_file,
    )
    while True:
        try:
            run_once()
        except Exception as exc:
            log.error("Poll error: %s", exc)
        time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()

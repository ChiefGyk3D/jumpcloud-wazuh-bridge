from __future__ import annotations

import argparse
import logging
import signal
import threading

from .client import JumpCloudClient
from .config import load_settings
from .poller import poll_once, save_cursor
from .writer import append_jsonl

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
log = logging.getLogger(__name__)

# Escalation thresholds for consecutive poll failures.
WARN_AFTER_FAILURES = 3
ERROR_AFTER_FAILURES = 5

# Set by SIGTERM/SIGINT; checked between poll cycles and used as an
# interruptible sleep so `docker stop` exits promptly and cleanly.
_shutdown = threading.Event()


def _handle_shutdown_signal(signum: int, frame: object) -> None:
    log.info("Received signal %s — shutting down after current cycle", signal.Signals(signum).name)
    _shutdown.set()


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


def run_loop(poll_seconds: int) -> None:
    """Continuous polling loop with consecutive-failure escalation.

    The cursor file's mtime only advances on success (save_cursor), so the
    container healthcheck correctly flags a bridge that keeps failing —
    deliberately, no heartbeat is written on failure.
    """
    consecutive_failures = 0
    while not _shutdown.is_set():
        try:
            run_once()
            consecutive_failures = 0
        except Exception:
            consecutive_failures += 1
            log.exception("Poll error (consecutive failures: %d)", consecutive_failures)
            if consecutive_failures >= ERROR_AFTER_FAILURES:
                log.error(
                    "%d consecutive poll failures — check the JumpCloud API key "
                    "and network connectivity",
                    consecutive_failures,
                )
            elif consecutive_failures >= WARN_AFTER_FAILURES:
                log.warning(
                    "%d consecutive poll failures — will keep retrying",
                    consecutive_failures,
                )
        # Event.wait returns early (True) when a shutdown signal arrives.
        _shutdown.wait(poll_seconds)
    log.info("Shutdown complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="JumpCloud -> Wazuh JSONL bridge")
    parser.add_argument("--once", action="store_true", help="Run one poll cycle and exit")
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    settings = load_settings()
    log.info(
        "Starting continuous polling (interval=%ds, services=%s, output=%s)",
        settings.poll_seconds,
        settings.services,
        settings.output_file,
    )
    run_loop(settings.poll_seconds)


if __name__ == "__main__":
    main()

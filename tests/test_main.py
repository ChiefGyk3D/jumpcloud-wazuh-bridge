import logging
import signal
import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from jumpcloud_wazuh_bridge import main as main_mod
from jumpcloud_wazuh_bridge.config import Settings

END_TIME = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)


def _settings(**overrides):
    base = {
        "api_key": "key",
        "base_url": "https://api.example.com",
        "org_id": "",
        "lookback_minutes": 15,
        "poll_seconds": 300,
        "output_file": "/data/out.jsonl",
        "state_file": "/data/cursor.json",
        "services": ["all"],
        "page_limit": 1000,
    }
    base.update(overrides)
    return Settings(**base)


class FakeShutdown:
    """Stand-in for the module's shutdown Event: stops after N wait() calls."""

    def __init__(self, cycles: int) -> None:
        self.cycles = cycles
        self.waits: list[float] = []

    def is_set(self) -> bool:
        return len(self.waits) >= self.cycles

    def wait(self, timeout: float | None = None) -> bool:
        self.waits.append(timeout)
        return self.is_set()

    def set(self) -> None:
        self.cycles = 0


# ------------------------------------------------------------------ run_once


def test_run_once_happy_path():
    events = [{"id": 1}, {"id": 2}]
    with patch.object(main_mod, "load_settings", return_value=_settings()), \
         patch.object(main_mod, "JumpCloudClient") as client_cls, \
         patch.object(main_mod, "poll_once", return_value=(events, END_TIME)) as poll, \
         patch.object(main_mod, "append_jsonl", return_value=2) as write, \
         patch.object(main_mod, "save_cursor") as save:
        written = main_mod.run_once()

    assert written == 2
    client_cls.assert_called_once_with(
        base_url="https://api.example.com", api_key="key", org_id=""
    )
    poll.assert_called_once_with(
        client_cls.return_value,
        "/data/cursor.json",
        15,
        services=["all"],
        page_limit=1000,
    )
    write.assert_called_once_with("/data/out.jsonl", events)
    # Cursor saved with the end time poll_once returned — only after a
    # successful write.
    save.assert_called_once_with("/data/cursor.json", END_TIME)


def test_run_once_requires_api_key():
    with patch.object(main_mod, "load_settings", return_value=_settings(api_key="")), \
         pytest.raises(SystemExit, match="JUMPCLOUD_API_KEY"):
        main_mod.run_once()


def test_run_once_does_not_save_cursor_when_write_fails():
    with patch.object(main_mod, "load_settings", return_value=_settings()), \
         patch.object(main_mod, "JumpCloudClient"), \
         patch.object(main_mod, "poll_once", return_value=([], END_TIME)), \
         patch.object(main_mod, "append_jsonl", side_effect=OSError("disk full")), \
         patch.object(main_mod, "save_cursor") as save, \
         pytest.raises(OSError):
        main_mod.run_once()
    save.assert_not_called()


# ------------------------------------------------------------------ run_loop


def test_run_loop_stops_on_shutdown_and_waits_poll_interval():
    fake = FakeShutdown(cycles=2)
    with patch.object(main_mod, "_shutdown", fake), \
         patch.object(main_mod, "run_once", return_value=0) as run:
        main_mod.run_loop(poll_seconds=42)
    assert run.call_count == 2
    assert fake.waits == [42, 42]


def test_run_loop_escalates_consecutive_failures(caplog):
    fake = FakeShutdown(cycles=5)
    with patch.object(main_mod, "_shutdown", fake), \
         patch.object(main_mod, "run_once", side_effect=RuntimeError("boom")), \
         caplog.at_level(logging.WARNING):
        main_mod.run_loop(poll_seconds=1)

    retrying = [
        r for r in caplog.records
        if "will keep retrying" in r.getMessage() and r.levelno == logging.WARNING
    ]
    check_hint = [
        r for r in caplog.records
        if "check the JumpCloud API key" in r.getMessage()
        and r.levelno == logging.ERROR
    ]
    # warning at 3 and 4 consecutive failures, error hint at 5
    assert len(retrying) == 2
    assert len(check_hint) == 1


def test_run_loop_resets_failure_counter_on_success(caplog):
    fake = FakeShutdown(cycles=4)
    side_effects = [RuntimeError("a"), RuntimeError("b"), 0, RuntimeError("c")]
    with patch.object(main_mod, "_shutdown", fake), \
         patch.object(main_mod, "run_once", side_effect=side_effects), \
         caplog.at_level(logging.WARNING):
        main_mod.run_loop(poll_seconds=1)

    # Failures never reach 3 in a row, so no escalation messages.
    assert not any("will keep retrying" in r.getMessage() for r in caplog.records)
    assert not any("check the JumpCloud API key" in r.getMessage() for r in caplog.records)


def test_run_loop_exits_immediately_when_already_shut_down():
    fake = FakeShutdown(cycles=0)
    with patch.object(main_mod, "_shutdown", fake), \
         patch.object(main_mod, "run_once") as run:
        main_mod.run_loop(poll_seconds=1)
    run.assert_not_called()


# ------------------------------------------------------------------- signals


def test_signal_handler_sets_shutdown_flag(monkeypatch):
    event = threading.Event()
    monkeypatch.setattr(main_mod, "_shutdown", event)
    main_mod._handle_shutdown_signal(signal.SIGTERM, None)
    assert event.is_set()


def test_main_registers_signal_handlers_and_runs_loop():
    registered: dict[int, object] = {}

    def fake_signal(signum, handler):
        registered[signum] = handler

    with patch.object(main_mod.signal, "signal", side_effect=fake_signal), \
         patch.object(main_mod, "load_settings", return_value=_settings(poll_seconds=7)), \
         patch.object(main_mod, "run_loop") as loop, \
         patch.object(main_mod.argparse.ArgumentParser, "parse_args",
                      return_value=MagicMock(once=False)):
        main_mod.main()

    assert registered[signal.SIGTERM] is main_mod._handle_shutdown_signal
    assert registered[signal.SIGINT] is main_mod._handle_shutdown_signal
    loop.assert_called_once_with(7)


def test_main_once_runs_single_cycle():
    with patch.object(main_mod, "run_once", return_value=0) as run, \
         patch.object(main_mod, "run_loop") as loop, \
         patch.object(main_mod.argparse.ArgumentParser, "parse_args",
                      return_value=MagicMock(once=True)):
        main_mod.main()
    run.assert_called_once()
    loop.assert_not_called()

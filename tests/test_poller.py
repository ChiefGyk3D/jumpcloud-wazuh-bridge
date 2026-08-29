import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from jumpcloud_wazuh_bridge.poller import (
    LAG_BUFFER_SECONDS,
    load_cursor,
    poll_once,
    save_cursor,
)


def test_cursor_roundtrip(tmp_path):
    state_file = str(tmp_path / "cursor.json")
    now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)

    save_cursor(state_file, now)
    loaded = load_cursor(state_file)
    assert loaded is not None
    assert loaded.year == 2026
    assert loaded.month == 3


def test_cursor_missing(tmp_path):
    assert load_cursor(str(tmp_path / "nope.json")) is None


def test_cursor_corrupt(tmp_path):
    bad = tmp_path / "cursor.json"
    bad.write_text("not json", encoding="utf-8")
    assert load_cursor(str(bad)) is None


def test_save_cursor_atomic(tmp_path):
    state_file = tmp_path / "cursor.json"
    now = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
    save_cursor(str(state_file), now)
    assert not (tmp_path / "cursor.json.tmp").exists()
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["last_end_time"] == "2026-03-08T12:00:00Z"


def test_poll_once_applies_lag_buffer(tmp_path):
    state_file = str(tmp_path / "cursor.json")
    cursor = datetime.now(timezone.utc) - timedelta(minutes=10)
    save_cursor(state_file, cursor)

    client = MagicMock()
    client.fetch_events.return_value = [{"a": 1}]

    before = datetime.now(timezone.utc)
    events, end_time = poll_once(client, state_file, lookback_minutes=15)
    after = datetime.now(timezone.utc)

    assert events == [{"a": 1}]
    assert before - timedelta(seconds=LAG_BUFFER_SECONDS) <= end_time
    assert end_time <= after - timedelta(seconds=LAG_BUFFER_SECONDS)
    kwargs = client.fetch_events.call_args.kwargs
    assert kwargs["end_time"] == end_time


def test_poll_once_skips_when_window_inside_lag_buffer(tmp_path):
    state_file = str(tmp_path / "cursor.json")
    cursor = datetime.now(timezone.utc) - timedelta(seconds=10)
    save_cursor(state_file, cursor)

    client = MagicMock()
    events, end_time = poll_once(client, state_file, lookback_minutes=15)

    assert events == []
    client.fetch_events.assert_not_called()
    # Returned end_time equals the stored cursor, so saving it does not
    # advance the cursor past unfetched events.
    assert end_time == load_cursor(state_file)

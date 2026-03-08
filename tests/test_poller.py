import json

from jumpcloud_wazuh_bridge.poller import load_cursor, save_cursor


def test_cursor_roundtrip(tmp_path):
    from datetime import datetime, timezone

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

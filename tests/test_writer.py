import json
import os
import stat

from jumpcloud_wazuh_bridge.writer import append_jsonl


def test_append_jsonl(tmp_path):
    out = tmp_path / "events.jsonl"
    n = append_jsonl(str(out), [{"a": 1}, {"b": 2}])
    assert n == 2
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    # Verify jumpcloud_bridge envelope
    for line in lines:
        parsed = json.loads(line)
        assert "jumpcloud_bridge" in parsed


def test_envelope_preserves_event_payload(tmp_path):
    out = tmp_path / "events.jsonl"
    event = {"service": "directory", "event_type": "admin_login_attempt", "n": 3}
    append_jsonl(str(out), [event])
    parsed = json.loads(out.read_text(encoding="utf-8").strip())
    assert parsed == {"jumpcloud_bridge": event}


def test_fresh_file_permissions_0600(tmp_path):
    out = tmp_path / "events.jsonl"
    append_jsonl(str(out), [{"a": 1}])
    mode = stat.S_IMODE(os.stat(out).st_mode)
    assert mode == 0o600


def test_append_behavior_across_calls(tmp_path):
    out = tmp_path / "events.jsonl"
    assert append_jsonl(str(out), [{"a": 1}]) == 1
    assert append_jsonl(str(out), [{"b": 2}, {"c": 3}]) == 2
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert json.loads(lines[0]) == {"jumpcloud_bridge": {"a": 1}}
    assert json.loads(lines[2]) == {"jumpcloud_bridge": {"c": 3}}


def test_empty_events_returns_zero_and_creates_file(tmp_path):
    out = tmp_path / "events.jsonl"
    assert append_jsonl(str(out), []) == 0
    assert out.exists()
    assert out.read_text(encoding="utf-8") == ""


def test_creates_parent_directories(tmp_path):
    out = tmp_path / "nested" / "dir" / "events.jsonl"
    assert append_jsonl(str(out), [{"a": 1}]) == 1
    assert out.exists()

import json

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

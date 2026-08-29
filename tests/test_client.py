from datetime import datetime, timezone
from unittest.mock import MagicMock

from jumpcloud_wazuh_bridge.client import JumpCloudClient

START = datetime(2026, 3, 8, 12, 0, 0, tzinfo=timezone.utc)
END = datetime(2026, 3, 8, 12, 5, 0, tzinfo=timezone.utc)


def _response(events, headers):
    resp = MagicMock()
    resp.json.return_value = events
    resp.headers = headers
    resp.raise_for_status.return_value = None
    return resp


def _client():
    return JumpCloudClient(base_url="https://api.example.com", api_key="key")


def test_fetch_events_paginates(monkeypatch):
    client = _client()
    pages = [
        _response(
            [{"id": 1}, {"id": 2}],
            {"X-Result-Count": "2", "X-Limit": "2", "X-Search_after": "[1]"},
        ),
        _response([{"id": 3}], {"X-Result-Count": "1", "X-Limit": "2"}),
    ]
    post = MagicMock(side_effect=pages)
    monkeypatch.setattr(client.session, "post", post)

    events = client.fetch_events(START, END, page_limit=2)
    assert [e["id"] for e in events] == [1, 2, 3]
    assert post.call_count == 2
    assert post.call_args_list[1].kwargs["json"]["search_after"] == [1]


def test_fetch_events_malformed_result_count(monkeypatch):
    client = _client()
    post = MagicMock(
        return_value=_response(
            [{"id": 1}], {"X-Result-Count": "garbage", "X-Limit": "2"}
        )
    )
    monkeypatch.setattr(client.session, "post", post)

    events = client.fetch_events(START, END, page_limit=2)
    assert [e["id"] for e in events] == [1]
    assert post.call_count == 1


def test_fetch_events_stale_search_after_breaks(monkeypatch):
    client = _client()
    # Server keeps returning the same cursor — must not loop forever
    post = MagicMock(
        return_value=_response(
            [{"id": 1}],
            {"X-Result-Count": "1", "X-Limit": "1", "X-Search_after": "[1]"},
        )
    )
    monkeypatch.setattr(client.session, "post", post)

    events = client.fetch_events(START, END, page_limit=1)
    assert post.call_count == 2
    assert len(events) == 2

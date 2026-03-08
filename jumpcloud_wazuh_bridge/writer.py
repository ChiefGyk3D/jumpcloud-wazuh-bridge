from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def append_jsonl(output_file: str, events: Iterable[dict[str, Any]]) -> int:
    """Write events as JSONL, wrapped in a jumpcloud_bridge envelope for Wazuh.

    Each line looks like:
      {"jumpcloud_bridge": {"service":"directory", "event_type":"admin_login_attempt", ...}}

    This envelope lets the Wazuh decoder key on "jumpcloud_bridge" reliably.
    """
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with path.open("a", encoding="utf-8") as f:
        for event in events:
            wrapped = {"jumpcloud_bridge": event}
            f.write(json.dumps(wrapped, ensure_ascii=True) + "\n")
            count += 1
    return count

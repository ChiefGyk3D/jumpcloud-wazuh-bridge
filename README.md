# JumpCloud Wazuh Bridge

Python poller that ingests [JumpCloud Directory Insights](https://docs.jumpcloud.com/api/insights/directory/1.0/index.html) events and writes them as JSONL for Wazuh.

## Features

- Polls JumpCloud Directory Insights API (`POST /insights/directory/v1/events`)
- Automatic pagination via `X-Search_after` headers (handles >1 000 events)
- Cursor-based state — only fetches new events each cycle
- Events wrapped in `{"jumpcloud_bridge": {...}}` envelope for reliable Wazuh decoding
- Configurable service filter (directory, sso, radius, ldap, systems, all, etc.)
- **Doppler-first secrets** — reads from Doppler CLI when available, falls back to env vars
- Multi-tenant support via `JUMPCLOUD_ORG_ID`

## Quick Start

```bash
pip install -r requirements.txt

# Option A: Doppler (recommended for production)
doppler run -- python3 -m jumpcloud_wazuh_bridge.main --once

# Option B: Environment variables
export JUMPCLOUD_API_KEY="your-read-only-api-key"
python3 -m jumpcloud_wazuh_bridge.main --once   # single poll
python3 -m jumpcloud_wazuh_bridge.main          # continuous loop
```

## Configuration

All settings resolve via: **Doppler → env var → default**.

| Variable | Default | Description |
|---|---|---|
| `JUMPCLOUD_API_KEY` | *(required)* | Read-only Directory Insights API key |
| `JUMPCLOUD_ORG_ID` | *(empty)* | Only needed for multi-tenant JumpCloud orgs |
| `JUMPCLOUD_BASE_URL` | `https://api.jumpcloud.com` | API base URL (use `https://console.eu.jumpcloud.com` for EU) |
| `JUMPCLOUD_SERVICES` | `all` | Comma-separated: `directory,sso,radius,ldap,systems,software,mdm,alerts` |
| `JUMPCLOUD_POLL_SECONDS` | `300` | Seconds between poll cycles (continuous mode) |
| `JUMPCLOUD_LOOKBACK_MINUTES` | `15` | Initial lookback window on first run |
| `JUMPCLOUD_OUTPUT_FILE` | `/tmp/jumpcloud-events.jsonl` | JSONL output path (Wazuh reads this) |
| `JUMPCLOUD_STATE_FILE` | `/tmp/jumpcloud-cursor.json` | Cursor persistence file |
| `JUMPCLOUD_PAGE_LIMIT` | `1000` | Events per API page (max 10 000) |

## Doppler Integration

This bridge uses [Doppler](https://www.doppler.com/) for secrets management when available.
If the `doppler` CLI is installed and configured, secrets are loaded automatically.
No code changes needed — just add your `JUMPCLOUD_API_KEY` to your Doppler project.

```bash
# Add your JumpCloud API key to Doppler
doppler secrets set JUMPCLOUD_API_KEY="your-key-here"

# Run with Doppler
doppler run -- python3 -m jumpcloud_wazuh_bridge.main
```

For environments without Doppler, set environment variables directly — the bridge
works identically either way.

## Wazuh Integration

Add a `<localfile>` entry to the Wazuh manager config:

```xml
<localfile>
  <log_format>json</log_format>
  <location>/var/ossec/logs/jumpcloud-events.jsonl</location>
</localfile>
```

Wazuh decoders and rules for JumpCloud events are provided in the
[siem-docker-stack](https://github.com/ChiefGyk3D/siem-docker-stack) repo under `wazuh/`.

## Event Services

JumpCloud Directory Insights covers these service types:

| Service | Events |
|---|---|
| `directory` | Admin/user CRUD, portal logins, group changes, policy updates |
| `sso` | SAML SSO authentication attempts |
| `radius` | RADIUS auth (Wi-Fi, VPN) |
| `ldap` | LDAP bind and search operations |
| `systems` | Device logins, password changes, lockouts, FDE key updates |
| `software` | Software add/change/remove on managed devices |
| `mdm` | MDM command results |
| `alerts` | JumpCloud alert events |
| `password_manager` | Password manager activity |
| `all` | Everything above |

## Layout

```
jumpcloud_wazuh_bridge/
  config.py   — Doppler + env var config resolution
  client.py   — JumpCloud API client with pagination
  poller.py   — Polling loop and cursor management
  writer.py   — JSONL output with jumpcloud_bridge envelope
  main.py     — CLI entrypoint (--once or continuous)
```

## License

MIT

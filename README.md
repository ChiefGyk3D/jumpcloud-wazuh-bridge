# JumpCloud Wazuh Bridge

Python poller that ingests [JumpCloud Directory Insights](https://docs.jumpcloud.com/api/insights/directory/1.0/index.html) events and writes them as JSONL for Wazuh.

## Features

- Polls JumpCloud Directory Insights API (`POST /insights/directory/v1/events`)
- Collects **all** service types: directory, sso, radius, ldap, systems, software, mdm, alerts, password_manager, access_management, asset_management, reports, saas_app_management, object_storage, notifications
- Automatic pagination via `X-Search_after` headers (handles >1 000 events)
- Cursor-based state — only fetches new events each cycle
- Events wrapped in `{"jumpcloud_bridge": {...}}` envelope for reliable Wazuh decoding
- **Doppler service token support** — no CLI install or login needed on production servers
- Three secrets modes: Doppler service token → Doppler CLI → plain env vars
- Docker-ready with included Dockerfile and docker-compose.yml
- Multi-tenant support via `JUMPCLOUD_ORG_ID`

## Quick Start

```bash
pip install -r requirements.txt

# Option A: Doppler service token (recommended for production / SIEM server)
# No Doppler CLI install or login needed — just one env var.
DOPPLER_TOKEN=dp.st.xxxx python3 -m jumpcloud_wazuh_bridge.main --once

# Option B: Doppler CLI (dev workstations)
doppler run -- python3 -m jumpcloud_wazuh_bridge.main --once

# Option C: Plain environment variables (no Doppler)
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

Secrets resolve in this order: **Doppler service token → Doppler CLI → env vars**.

### Production (SIEM server) — Service Token

The recommended way to run on the SIEM server. No Doppler CLI install or
`doppler login` required. The token is scoped to exactly one project+config
and cannot access anything else.

1. In the [Doppler dashboard](https://dashboard.doppler.com), go to your project
   (e.g., `siem-pfsense`) → `prd` config → **Access** → **Service Tokens**
2. Generate a token (e.g., name it `siem-jumpcloud-bridge`)
3. On the SIEM server, set `DOPPLER_TOKEN=dp.st.xxxx` as an environment variable
   (in your Docker compose, systemd unit, or `.env` file)

The bridge calls the Doppler HTTP API directly with this token — no CLI needed.

### Development — Doppler CLI

On dev workstations where you have the Doppler CLI installed:

```bash
doppler setup --project siem-pfsense --config prd
doppler run -- python3 -m jumpcloud_wazuh_bridge.main --once
```

### No Doppler

Set environment variables directly — the bridge works identically either way:

```bash
export JUMPCLOUD_API_KEY="your-key"
python3 -m jumpcloud_wazuh_bridge.main
```

## Docker Deployment

For running on the SIEM server alongside the rest of the stack:

```bash
# Build and run
docker compose up -d --build

# Check logs
docker logs jumpcloud-bridge -f
```

Set secrets via environment in `docker-compose.yml`:

```yaml
environment:
  DOPPLER_TOKEN: dp.st.xxxx          # Option 1: Doppler service token
  # JUMPCLOUD_API_KEY: your-key      # Option 2: direct env var
```

The JSONL output volume (`jumpcloud-data`) should be accessible to the Wazuh
manager container so it can read events via `<localfile>`.

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

JumpCloud Directory Insights covers these service types (default: `all`):

| Service | Events |
|---|---|
| `directory` | Admin/user CRUD, portal logins, group changes, policy updates |
| `sso` | SAML/OIDC SSO authentication attempts |
| `radius` | RADIUS auth (Wi-Fi, VPN) |
| `ldap` | LDAP bind and search operations |
| `systems` | Device logins, password changes, lockouts, FDE key updates |
| `software` | Software add/change/remove on managed devices |
| `mdm` | MDM command results |
| `alerts` | JumpCloud alert events |
| `password_manager` | Password manager activity |
| `access_management` | Access management events |
| `asset_management` | Asset tracking events |
| `reports` | Report generation events |
| `saas_app_management` | SaaS app management |
| `object_storage` | Object storage events |
| `notifications` | Notification events |
| **`all`** | **Everything above (default)** |

## Layout

```
jumpcloud_wazuh_bridge/
  config.py   — Doppler service token + CLI + env var config resolution
  client.py   — JumpCloud API client with pagination
  poller.py   — Polling loop and cursor management
  writer.py   — JSONL output with jumpcloud_bridge envelope
  main.py     — CLI entrypoint (--once or continuous)
dashboards/
  jumpcloud_security.json — Grafana dashboard (14 panels, datasource template var)
scripts/
  deploy-dashboard.py     — Deploy dashboard to Grafana via API
Dockerfile                — Production container image (hardened, non-root)
docker-compose.yml        — Ready-to-use compose service
tests/                    — Unit tests
```

## Grafana Dashboard

A dedicated **JumpCloud IdP Security** dashboard is included with 14 panels:

- Auth failures/success timelines and stats
- Brute-force alerts, policy changes, MFA events
- Events by service (pie chart) and event type (bar chart)
- SSO application usage
- Auth failures by source IP
- User lifecycle timeline
- Recent events table with field renaming

### Import Dashboard

```bash
# Via deploy script
GRAFANA_URL="http://localhost:3000" \
GRAFANA_USER="admin" \
GRAFANA_PASS="changeme" \
python3 scripts/deploy-dashboard.py

# Or import manually: Grafana → Dashboards → New → Import → Upload JSON
# File: dashboards/jumpcloud_security.json
```

The dashboard uses a `${ds}` datasource template variable — select your OpenSearch/Wazuh datasource from the dropdown after import.

A summary view of JumpCloud events is also included in the **SIEM+ Overview** dashboard in the [siem-docker-stack](https://github.com/ChiefGyk3D/siem-docker-stack) repo.

## License

MIT

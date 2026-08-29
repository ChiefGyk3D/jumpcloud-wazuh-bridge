# Roadmap

Plan for the JumpCloud → Wazuh bridge, established after the August 2026 cross-stack review. The stack-wide game plan lives in [siem-docker-stack/docs/game-plan.md](https://github.com/ChiefGyk3D/siem-docker-stack/blob/master/docs/game-plan.md).

## Landed in the 2026-08 review

- Fixed the dead ruleset: `wazuh/rules/jumpcloud_rules.xml` chained off `decoded_as json` while the shipped decoder registers `jumpcloud_bridge`, so no rule could ever fire
- 90s ingestion-lag buffer on the polling window (late-indexed events were silently skipped forever)
- Retry/backoff on the JumpCloud API session; pagination guards (malformed headers, stale cursor, max pages)
- Atomic cursor writes; 0600 output file permissions
- Container healthcheck now detects a *stalled* bridge (cursor freshness, not existence)
- `python -m jumpcloud_wazuh_bridge` works (fixes the systemd unit documented in siem-docker-stack)
- MIT LICENSE file (README already claimed MIT); unused deps dropped; Ruff enforced in CI; client/poller test coverage

## Next up (hardening)

- [ ] **Decide detection ownership** with siem-docker-stack: this repo ships rules 100300–100350, the stack ships 120600–120681 for the same events — installing both double-alerts. Recommendation: the stack owns detections; this repo's `wazuh/` becomes the standalone-only alternative or is removed. Same for the `jumpcloud_security` dashboard (one `uid`, one owner).
- [ ] **Streamed backfill**: pages are buffered fully in memory before writing; a week-long outage plus a big org risks OOM crash-loops. Stream each page to disk, checkpoint per page, slice large windows.
- [ ] **Event-ID dedup** across window boundaries (second-precision cursors re-emit boundary events).
- [ ] **Output rotation**: the JSONL sink grows forever — ship a logrotate snippet or size-based rotation that Wazuh's tailer tolerates.
- [ ] **Failure escalation**: consecutive-failure counter surfaced via the healthcheck/heartbeat instead of one log line per failed cycle.
- [ ] **Compose hardening**: `read_only`, `cap_drop: [ALL]`, `no-new-privileges`, resource limits, `env_file`/secrets instead of plain `environment:`; document the published ghcr.io image instead of `build: .`.
- [ ] **Packaging**: `pyproject.toml`, pinned/locked deps, digest-pinned base image.
- [ ] **Config validation**: reject `poll_seconds <= 0`, non-numeric values, unknown service names; clamp stale cursors to JumpCloud's retention window.

## Later / nice-to-have

- [ ] SIEM Overview dashboard row + n8n JumpCloud triage workflow (tracked in siem-docker-stack roadmap Phase 1)
- [ ] Make CI security scanners (Bandit, pip-audit) blocking once baselined
- [ ] `SECURITY.md` + release/versioning discipline for the published image

**Maintainer:** [ChiefGyk3D](https://github.com/ChiefGyk3D)

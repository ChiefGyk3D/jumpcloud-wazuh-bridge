FROM python:3.14-slim

# Build args for multi-arch (set automatically by buildx)
ARG TARGETPLATFORM
ARG BUILDPLATFORM

WORKDIR /app

# Non-root user for security
RUN groupadd -r bridge && useradd -r -g bridge -d /app -s /sbin/nologin bridge

# Upgrade pip to fix CVE-2025-8869, install deps, remove build cache
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade "pip>=25.3" && \
    pip install --no-cache-dir -r requirements.txt

COPY jumpcloud_wazuh_bridge/ jumpcloud_wazuh_bridge/

# Output and state persisted via volume mount
RUN mkdir -p /data && chown bridge:bridge /data
VOLUME ["/data"]

ENV JUMPCLOUD_OUTPUT_FILE=/data/jumpcloud-events.jsonl
ENV JUMPCLOUD_STATE_FILE=/data/cursor.json

# Drop to non-root
USER bridge

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "from pathlib import Path; import sys; p=Path('/data/cursor.json'); sys.exit(0 if p.exists() else 1)"

ENTRYPOINT ["python3", "-m", "jumpcloud_wazuh_bridge.main"]

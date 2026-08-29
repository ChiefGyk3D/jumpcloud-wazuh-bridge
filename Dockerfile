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

ENV PYTHONUNBUFFERED=1
ENV JUMPCLOUD_OUTPUT_FILE=/data/jumpcloud-events.jsonl
ENV JUMPCLOUD_STATE_FILE=/data/cursor.json

# Drop to non-root
USER bridge

# Healthy when the cursor file has been updated within 3x the poll interval
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s --retries=3 \
  CMD python3 -c "import os, sys, time; v = os.environ.get('JUMPCLOUD_POLL_SECONDS', '300'); i = int(v) if v.isdigit() else 300; p = os.environ.get('JUMPCLOUD_STATE_FILE', '/data/cursor.json'); sys.exit(0 if os.path.exists(p) and time.time() - os.path.getmtime(p) < 3 * i else 1)"

ENTRYPOINT ["python3", "-m", "jumpcloud_wazuh_bridge.main"]

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY jumpcloud_wazuh_bridge/ jumpcloud_wazuh_bridge/

# Output and state persisted via volume mounts
VOLUME ["/data"]

ENV JUMPCLOUD_OUTPUT_FILE=/data/jumpcloud-events.jsonl
ENV JUMPCLOUD_STATE_FILE=/data/cursor.json

ENTRYPOINT ["python3", "-m", "jumpcloud_wazuh_bridge.main"]

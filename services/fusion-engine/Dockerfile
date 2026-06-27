# Fusion engine image. Build context is the REPO ROOT (see deploy/docker-compose.yml) so the
# service can ship with config/ at the same relative layout it uses on a dev box — __main__.py
# resolves REPO = parents[3], i.e. /app, so /app/config/*.example.json are the defaults.
FROM python:3.11-slim

WORKDIR /app

# deps first for layer caching
COPY services/fusion-engine/requirements.txt services/fusion-engine/requirements.txt
RUN pip install --no-cache-dir -r services/fusion-engine/requirements.txt

# frozen contract config + the service code (parity: same configs the sim/L3 use)
COPY config/ config/
COPY services/fusion-engine/ services/fusion-engine/

# Drop root (least privilege): run as a dedicated non-root user. /app/logs is created and owned by
# it so a fresh named volume inherits writable ownership. NOTE: the shipped compose bind-mounts the
# host ./logs here — on a host that enforces bind-mount ownership (native Linux) that dir must be
# writable by UID 10001 (CI chmods it; Docker Desktop bind mounts are already permissive).
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /app/logs && chown -R app:app /app/logs

ENV PYTHONUNBUFFERED=1
WORKDIR /app/services/fusion-engine
USER app

# --host broker = the compose service name; logs to a mounted volume for log_replay reproducibility
CMD ["python", "-m", "fusion", "--host", "broker", "--log-dir", "/app/logs"]

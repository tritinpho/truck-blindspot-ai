# In-cabin HMI image — build the Vite bundle, serve it static with nginx (kiosk-style).
# Build context is the REPO ROOT (see deploy/docker-compose.yml).
#
# The HMI single-sources the zone map from the repo-root config/ (apps/hmi/src/config.ts imports
# ../../../config/zones.example.json, FR-03 — no duplicated copy). So the build stage mirrors the
# repo layout — apps/hmi at /app/apps/hmi, config/ at /app/config — and builds from there; that
# relative import resolves at tsc/vite-build time exactly as it does on a dev box. (Flattening
# apps/hmi straight into /app drops config/ out of the tree and fails the build with TS2307.)
#
# The browser runs on the host and talks to the broker's published WebSocket port directly, so the
# default ws://localhost:9001 (main.ts) needs no configuration for the dev demo. Override at build
# time with --build-arg VITE_BROKER_WS=ws://<host>:9001 for a kiosk on a different machine.
FROM node:20-alpine AS build
WORKDIR /app/apps/hmi
# deps first for layer caching
COPY apps/hmi/package.json apps/hmi/package-lock.json ./
RUN npm ci
COPY apps/hmi/ ./
# single source of truth for the zone geometry (see header) — must sit at /app/config
COPY config/ /app/config/
ARG VITE_BROKER_WS
RUN npm run build

# Serve non-root (least privilege): the -unprivileged image runs as user nginx (UID 101) and listens
# on 8080 instead of 80 (binding :80 is what would need root). Static assets are world-readable, so
# no chown is needed. The published port is remapped to 8080 in deploy/docker-compose.yml.
FROM nginxinc/nginx-unprivileged:alpine
COPY --from=build /app/apps/hmi/dist /usr/share/nginx/html
EXPOSE 8080

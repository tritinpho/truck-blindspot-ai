# In-cabin HMI image — build the Vite bundle, serve it static with nginx (kiosk-style).
# Build context is the REPO ROOT (see deploy/docker-compose.yml).
#
# The browser runs on the host and talks to the broker's published WebSocket port directly, so the
# default ws://localhost:9001 (main.ts) needs no configuration for the dev demo. Override at build
# time with --build-arg VITE_BROKER_WS=ws://<host>:9001 for a kiosk on a different machine.
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/hmi/package.json apps/hmi/package-lock.json ./
RUN npm ci
COPY apps/hmi/ ./
ARG VITE_BROKER_WS
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

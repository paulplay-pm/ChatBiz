# syntax=docker/dockerfile:1.7
# =====================================================================
# ChatBiz Web — unified SPA runtime (multi-stage)
#
# Stage 1 (builder): install pnpm + run 3 vite builds inside node:20-alpine.
# Stage 2 (runtime): copy dist/ + nginx.conf into nginx:1.27-alpine.
#
# Sub-app VITE_APP_BASE values match web/nginx.conf location prefixes:
#   /portal/  /canvas/  /admin/
#
# Pre-existing convention: dev compose bind-mounts ../web:/app, so source
# changes are picked up by `pnpm build` on next `docker compose build`.
# =====================================================================

# ---------- builder ---------------------------------------------------------
FROM node:20-alpine AS builder

# Enable pnpm via corepack (ships with node:20-alpine). Pin to 9.x to match
# web/pnpm-lock.yaml lockfileVersion.
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate

WORKDIR /app

# Copy lockfile + workspace manifest + package manifests first to maximize
# layer cache. pnpm-workspace.yaml MUST be present before `pnpm install`,
# otherwise pnpm falls back to "root only" and silently skips workspace
# members (admin/canvas/portal), which then fail tsc with TS2307 on every
# dep that lives in a sub-app's package.json.
COPY pnpm-workspace.yaml pnpm-lock.yaml package.json ./
COPY portal/package.json ./portal/package.json
COPY canvas/package.json ./canvas/package.json
COPY admin/package.json ./admin/package.json

# Install root + all sub-app deps from the workspace layout.
# --frozen-lockfile pins to pnpm-lock.yaml (no version drift).
RUN pnpm install --frozen-lockfile

# Copy the rest of the source (Dockerfile, nginx.conf, sub-app sources).
COPY . .

# Build each sub-app with its VITE_APP_BASE matching nginx.conf location.
ARG VITE_APP_BASE_PORTAL=/portal/
ARG VITE_APP_BASE_CANVAS=/canvas/
ARG VITE_APP_BASE_ADMIN=/admin/

RUN VITE_APP_BASE=${VITE_APP_BASE_PORTAL} pnpm --dir portal build
RUN VITE_APP_BASE=${VITE_APP_BASE_CANVAS} pnpm --dir canvas build
RUN VITE_APP_BASE=${VITE_APP_BASE_ADMIN} pnpm --dir admin build

# ---------- runtime ---------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Install libcap to grant the unprivileged web user CAP_NET_BIND_SERVICE
# (so it can bind port 80 without running as root). Matches the sso /
# credential pattern: non-root user, uid 10001.
RUN apk add --no-cache libcap

# Create unprivileged user. nginx:1.27-alpine ships a built-in 'nginx' user
# (uid 101), but we use 10001 to align with the rest of the ChatBiz compose
# stack (see services/sso/Dockerfile, services/credential/Dockerfile).
RUN addgroup -g 10001 -S web && adduser -u 10001 -S -G web -h /var/cache/nginx -s /sbin/nologin web

# Grant the nginx binary CAP_NET_BIND_SERVICE so the 'web' user can bind
# port 80 without root. Required because EXPOSE 80 is a privileged port.
RUN setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx

# Copy built SPA bundles (owned by the unprivileged web user) and the
# nginx config into the runtime image.
COPY --chown=web:web --from=builder /app/portal/dist /usr/share/nginx/html/portal
COPY --chown=web:web --from=builder /app/canvas/dist /usr/share/nginx/html/canvas
COPY --chown=web:web --from=builder /app/admin/dist /usr/share/nginx/html/admin
COPY --chown=web:web --from=builder /app/index.html /usr/share/nginx/html/index.html
COPY --chown=web:web --from=builder /app/nginx.conf /etc/nginx/conf.d/default.conf

# Ensure nginx runtime paths (pid file, temp dirs) are writable by 'web'.
# nginx:1.27-alpine's default.conf uses /var/run/nginx.pid and /var/cache/nginx.
RUN touch /var/run/nginx.pid && chown -R web:web /var/run/nginx.pid /var/cache/nginx /usr/share/nginx/html

EXPOSE 80

USER web

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["wget", "-qO-", "http://127.0.0.1:80/health"]

CMD ["nginx", "-g", "daemon off;"]

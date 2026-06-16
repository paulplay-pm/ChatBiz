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

# Copy lockfile + package manifests first to maximize layer cache.
COPY pnpm-lock.yaml package.json ./
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

COPY --from=builder /app/portal/dist /usr/share/nginx/html/portal
COPY --from=builder /app/canvas/dist /usr/share/nginx/html/canvas
COPY --from=builder /app/admin/dist /usr/share/nginx/html/admin
COPY --from=builder /app/index.html /usr/share/nginx/html/index.html
COPY --from=builder /app/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["wget", "-qO-", "http://127.0.0.1:80/health"]

CMD ["nginx", "-g", "daemon off;"]

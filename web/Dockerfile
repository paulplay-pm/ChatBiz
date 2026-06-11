# syntax=docker/dockerfile:1.7
# =====================================================================
# ChatBiz Web — unified SPA container
#
# 本容器包含：
#   - canvas       — 可视化画布（workflow 编辑器 + 调试器 + 列表）
#   - chatflow     — Chatflow 对话界面
#   - (future) settings / dashboard / admin-entry 等前端能力
#
# 多阶段构建：
#   dev      → node:22-alpine + pnpm install + Vite dev server (HMR)
#   builder  → pnpm build → dist/
#   runtime  → nginx serve dist/ + SPA fallback + API proxy
# =====================================================================

# ---------- dev ----------
FROM node:22-alpine AS dev
ENV CI=true
WORKDIR /app/canvas
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile --ignore-scripts
COPY . .
EXPOSE 5173
# run dev with inline --no-install so pnpm doesn't try to purge node_modules
# on startup (named volume already has them from the build)
CMD ["sh", "-c", "exec pnpm dev --host 0.0.0.0 --no-install"]

# ---------- builder ----------
FROM dev AS builder
RUN pnpm build

# ---------- runtime ----------
FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/canvas/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["wget", "-qO-", "http://127.0.0.1:80/health"]

CMD ["nginx", "-g", "daemon off;"]

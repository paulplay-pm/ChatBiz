# syntax=docker/dockerfile:1.7
# =====================================================================
# ChatBiz Web — unified SPA runtime
#
# 前置：先在本地分别 build 好：
#   cd web/canvas    && VITE_APP_BASE=/canvas/    pnpm exec vite build
#   cd web/admin-web && VITE_APP_BASE=/admin-web/ pnpm build
#
# 然后本 Dockerfile 只负责把产物打包进 nginx。
# =====================================================================

FROM nginx:1.27-alpine AS runtime
COPY index.html /usr/share/nginx/html/index.html
COPY canvas/dist /usr/share/nginx/html/canvas
COPY admin-web/dist /usr/share/nginx/html/admin-web
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD ["wget", "-qO-", "http://127.0.0.1:80/health"]

CMD ["nginx", "-g", "daemon off;"]

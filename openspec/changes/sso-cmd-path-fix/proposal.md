# sso-cmd-path-fix — Proposal

## Why

`services/sso/Dockerfile` 跟 `infrastructure/docker-compose-dev.yml` 段 `sso:` 的 `uvicorn app.main:app` 路径不匹配 — Dockerfile 把源码装到 `/home/sso/app/`,但 `uvicorn app.main:app` 在 WORKDIR 下找 `app/main.py` (即 `/app/app/`)。

后果: 容器启动时 `Error: Invalid value for '--reload-dir': Path '/app/app' does not exist`,`chatbiz-sso-1` Exited (2)。dev compose `chatbiz-web` 段的 3-gate `depends_on: sso: service_healthy` 失败,cascade 到 `chatbiz-mcp` + `chatbiz-workflow-engine`。整个 stack 起不来。

**这是 sso-real-impl (archive 2026-06-14) 没解决的预存问题**,该 change 注释 (Dockerfile 第 7 行) 明文说 "the image will build, but the default CMD will fail until the FastAPI app is wired in"。sso-real-impl 写了 Python 源文件,没改 Dockerfile WORKDIR 跟 source COPY 路径 mismatch。

## What Changes

- **修改** `services/sso/Dockerfile` 第 36 + 41 行: `WORKDIR /home/sso` → `WORKDIR /app` + `COPY --chown=chatbiz-sso:chatbiz-sso . /home/sso` → `COPY --chown=chatbiz-sso:chatbiz-sso . /app`,让源码装到 `/app/app/` 跟 `uvicorn app.main:app` 期望一致
- **不** 改 Python 后端源码 (本 change 0 行 Python)
- **不** 改 `infrastructure/docker-compose.yml` 或 `infrastructure/docker-compose-dev.yml` (uvicorn command 期望 `/app/app/`,改 Dockerfile 即可)
- **不** 改 `services/sso/app/main.py` 等已写好的 Python 源文件 (sso-real-impl 已实施)
- **不** 写新 capability (这是 fix-up,不是新功能)

## Capabilities

### New Capabilities

无。这是 sso Dockerfile WORKDIR/COPY 路径 mismatch 修,不是新 capability。

### Modified Capabilities

- `sso-real-impl` (existing capability, archive 2026-06-14): **前端范围** = N/A (无前端变更);**后端范围** = 0 (Python 源码不动);**是否豁免前端** = 是 — 纯 Dockerfile WORKDIR/COPY 路径修,跟前端 0 关系。

## Impact

- **新开发者 onboarding**: 跑 `docker compose -f ... -f ... up -d` 后 `chatbiz-sso-1` 起 healthy,`chatbiz-mcp` + `chatbiz-workflow-engine` 的 3-gate health gate 通过,stack ready
- **CI**: 不动 `.github/workflows/ci-cov.yml` (sso cov 矩阵已含,本 change 跟 cov 0 关系)
- **生产部署**: 不影响 (生产 K8s 走 sso Deployment 自己的 image tag + command,跟 dev compose 的 uvicorn reload 模式无关)
- **测试**: 不需要写新 unit test (本 change 0 行 Python,跟 cov 无关)。`sso-user-line-45` / `sso-wechat-coverage` / `sso-routers-coverage` 3 个 cov change 不受影响
- **被消费的下游**: 4 个依赖 sso 的 service (`mcp` / `workflow-engine` / `chatbiz-web` 3-gate) 都能起,`fix-migrate-hostname` 改的 `depends_on: sso: service_healthy` 在 dev overlay 才能真正生效

## Non-goals

1. **不** 改 Python 后端源码
2. **不** 改 dev / base / test / e2e-ha compose
3. **不** 写新 capability
4. **不** 改 `infrastructure/README.md` 文档
5. **不** 改 sso Dockerfile 的 healthcheck 命令 (uvicorn 起后 `/healthz` 端点走 `sso/chatbiz-sso` Python source,WORKDIR 改了但 healthcheck 端点不变,正常)
6. **不** 升级 python 3.12 → 3.13
7. **不** 改 `sso-real-impl` change 的 retro (sso-real-impl retro 应 surface 这个 followup,本 change 不重写)

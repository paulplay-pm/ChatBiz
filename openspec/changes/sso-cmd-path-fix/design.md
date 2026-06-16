# sso-cmd-path-fix — Design

## Context

`services/sso/Dockerfile` 第 36 + 41 行装源码到 `/home/sso/app/`,但 `uvicorn app.main:app` (Dockerfile line 54 CMD + dev compose line 215-220 command) 期望 `app/` 在 `/app/app/`。结果容器启动 fail: `Error: Invalid value for '--reload-dir': Path '/app/app' does not exist`。

`sso-real-impl` (archive 2026-06-14) 写了 `services/sso/app/main.py` 等 Python 源文件,但 Dockerfile WORKDIR 没改,跟源码所在路径不匹配。这是 sso-real-impl 当时没 surface 的 followup。

后果链(本 session 2026-06-16 实测):
- `chatbiz-sso-1` Exited (2) → 
- dev compose `chatbiz-web` 段 3-gate `depends_on: sso: service_healthy` 失败 →
- `chatbiz-mcp` + `chatbiz-workflow-engine` 同样 fail
- `chatbiz-web` 自身 Recreated 但实际未 ready (没 nginx upstream 健康)
- `chatbiz-credential` / `chatbiz-audit-isolation` healthy

上游三件源:本 change 不触 `docs/architecture.md` / `docs/prd.md` / design doc(无新增架构层、无产品需求变更、无 eng-review 决策冲突)。

## Goals / Non-Goals

**Goals** (1 条):
1. 改 `services/sso/Dockerfile` 2 行 (`WORKDIR` + `COPY` 目标),让 sso 容器能起来

**Non-Goals** (5 条,显式 YAGNI):
1. **不** 改 Python 后端源码 (sso-real-impl 已实施)
2. **不** 改任何 compose 文件 (uvicorn command 期望 `/app/app/`,改 Dockerfile 即可对齐)
3. **不** 改 sso Dockerfile 的 healthcheck (uvicorn 起后 `/healthz` 走 Python 源,WORKDIR 改了不影响)
4. **不** 升级 python 3.12 → 3.13
5. **不** 改 `sso-real-impl` 的 retro (sso-real-impl retro 应 surface 这 followup,本 change 不重写)

## Decisions

### D1: 改 Dockerfile (WORKDIR + COPY),不动 compose

**Context**: Dockerfile line 36 + 41 装源码到 `/home/sso/app/`,但 uvicorn 期望 `/app/app/`。两条路径都引到 `/app/`。

**选项**:
- **A (已选)**: 改 Dockerfile line 36 `WORKDIR /home/sso` → `WORKDIR /app` + line 41 `COPY --chown=chatbiz-sso:chatbiz-sso . /home/sso` → `COPY --chown=chatbiz-sso:chatbiz-sso . /app`。2 行,1 commit
- B: 改 dev compose + Dockerfile CMD `uvicorn app.main:app` → `uvicorn /home/sso.app.main:app` (用 PYTHONPATH 或 module path) — 拒绝理由:更脆弱,要改多文件,跟 sso-real-impl 的 README 文档不一致
- C: 改 Dockerfile line 36 + 41 不动,但加一个 RUN `mkdir -p /app && ln -s /home/sso/app /app/app` — 拒绝理由:YAGNI,加 symlink 治标不治本

**结论**: 选 A,2 行最小修改。

### D2: 验证方法

**Context**: 修后必须验证 sso 容器真起。

**选项**:
- **A (已选)**: `docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso` + `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` + 60s wait + `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` 期望 `(healthy)`
- B: 只跑 `docker build` 不跑 compose — 拒绝理由:不够,不能确认 sso-1 真的起

**结论**: 选 A。

## Risks / Trade-offs

- **Risk 1 (低)**: WORKDIR 改了后,如果 `sso/chatbiz-sso` non-root user 的 `~/.local/lib/python3.12/site-packages` 路径不变,`import app` 应该还能找到 `app/`(因为 `import app` 只看 python module search path,不看 cwd)。但**uvicorn 在 `--reload-dir` 模式下会检查 cwd 下的目录**,所以 WORKDIR 必须指向含 `app/` 的目录。改到 `/app` 满足这一点
- **Risk 2 (低)**: 改后 `PATH=/home/chatbiz-sso/.local/bin:$PATH` env 仍指向 non-root user 的 pip bin,跟 WORKDIR 无关(环境变量跟 cwd 无关),所以仍能 work
- **Risk 3 (低)**: sso Dockerfile 第 7 行注释 "the image will build, but the default CMD will fail" — 修后应改注释为 "now wired up correctly"。**本 change 不在 spec scope,可在 followup #1 顺手改**

## Migration Plan

| # | Step | 产物 |
|---|---|---|
| 1 | 改 Dockerfile line 36 + 41 | 2 行修改 |
| 2 | `git diff services/sso/Dockerfile` 验证只改 2 行 | 1 file, 2 insertions, 2 deletions |
| 3 | `git add services/sso/Dockerfile && git commit -m "fix(sso): align WORKDIR + COPY target to /app so uvicorn can find app/main.py"` | 1 commit |
| 4 | `docker build` sso image | `chatbiz/sso:dev` image 重建 |
| 5 | `docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d` 跑 60s,期望 sso-1 (healthy),mcp + workflow-engine (healthy) | 端到端验证 |

**Rollback**: 任何步骤失败 → `git revert` 已 push 的 commits。

## Verification

| # | 验证项 | 命令 | 期望 |
|---|---|---|---|
| V1 | Dockerfile 改 2 行 | `git diff services/sso/Dockerfile` | 2 行 +,2 行 - |
| V2 | sso image rebuild 成功 | `docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso` | exit 0, 镜像 `chatbiz/sso:dev` 重建 |
| V3 | sso-1 (healthy) | `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` | `(healthy)` |
| V4 | mcp + workflow-engine (healthy) | `docker ps --filter name=chatbiz-mcp --filter name=chatbiz-workflow-engine --format "{{.Names}}: {{.Status}}"` | 2 行 `(healthy)` |
| V5 | sso-1 healthcheck 端点 | `curl -fsS http://localhost:8007/healthz` (走 host port,需要在 compose 加 port map) — 替代:`docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"` | `200` |

## Open Questions

无。trivial 2-line fix,无 Open Questions 段。如果 V3/V4 失败,需要回到 D1 重新分析(可能 sso Python source 还缺其他文件,sso-real-impl 没全实施)。

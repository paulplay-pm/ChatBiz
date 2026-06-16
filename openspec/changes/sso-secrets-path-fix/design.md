# sso-secrets-path-fix — Design

## Context

`sso-cmd-path-fix` (2026-06-16) 修了 sso Dockerfile 的 WORKDIR + COPY 路径,`chatbiz-sso-1` 从 `Exited (2)` 升到 `Up (unhealthy)`。但 `lifespan.py:60-61` 的 `JWT_PRIVATE_KEY_PATH` 默认值是 `secrets/jwt_private.pem` 相对路径,容器内 resolve 为 `/app/secrets/jwt_private.pem`。`jwt_utils.py:91` 调 `private_path.parent.mkdir(parents=True, exist_ok=True)` 要创 `/app/secrets/` 目录,但 sso Dockerfile:43 用 `USER chatbiz-sso` 切非 root user,`/app` owner 是 root,非 root user 无 write permission → `PermissionError: [Errno 13] Permission denied: 'secrets'`。

`sso-real-impl` (archive 2026-06-14) 当时没 surface 这个问题 — `lifespan.py` 在 host 开发环境 work (cwd 是 dev 用户的 home,可写),但容器内 cwd 是 `/app` 且非 root user 无写权限。属于 "host develop OK, container fail" 的典型 pre-existing。

后果链(本 session 2026-06-16 实测):
- `chatbiz-sso-1` Up (unhealthy) →
- `chatbiz-web` 3-gate `depends_on: sso: service_healthy` 失败 →
- Web SSO 端到端不可用 (`curl /api/auth/sso/jwks.json` 502)

上游三件源:本 change 不触 `docs/architecture.md` / `docs/prd.md` / design doc(无新增架构层、无产品需求变更、无 eng-review 决策冲突)。

## Goals / Non-Goals

**Goals** (1 条):
1. 改 `services/sso/app/lifespan.py:60-61` 默认值,让 sso 容器 RSA key path 用 non-root user 可写路径

**Non-Goals** (5 条,显式 YAGNI):
1. **不** 改 `services/sso/Dockerfile` (HOME 已是 `/home/chatbiz-sso`,非 root user 拥有 $HOME,不需要 mkdir/chown)
2. **不** 改 `services/sso/.env.example` (默认值升级,显式覆盖仍 work)
3. **不** 改 `services/sso/app/jwt_utils.py` (函数实现正确,只改 lifespan.py 传入的 default)
4. **不** 改 `infrastructure/docker-compose*.yml` (无 env var 改动)
5. **不** 改 `.github/workflows/ci-cov.yml` (跟 cov 0 关系)

## Decisions

### D1: 改默认值到 `~/.sso/secrets/` (home-relative)

**Context**: 需要让 RSA key path 在 non-root user 下可写。`/app` 不可写 (root 拥有),`/home/chatbiz-sso` 可写 (non-root user 拥有)。

**选项**:
- **A (已选)**: lifespan.py:60-61 改默认值到 `"~/.sso/secrets/jwt_private.pem"`,`~` 在 Path constructor 中 expand 为 `$HOME` (= `/home/chatbiz-sso`)。2 行,1 commit
- B: Dockerfile 加 `RUN mkdir -p /app/secrets && chown chatbiz-sso:chatbiz-sso /app/secrets` + 保留 lifespan.py 默认值 — 拒绝理由:在 WORKDIR 写 `secrets/` 子目录是反模式,production K8s 通常 mount secret 进来,不应该 hardcode 容器内 path
- C: lifespan.py 改默认值到 `os.path.expanduser("~/.sso/secrets/jwt_private.pem")` 显式 expand — 拒绝理由:`Path("~")` 自动 expand (Python 3.13+? 不,在 pathlib.Path 不自动 expand;但 `os.path.expanduser` 可显式 expand。**实测:Path("~/.foo").expanduser() works**),所以用 `Path()` 加字符串 `~` 也 work
- D: 用 `tempfile.gettempdir()` — 拒绝理由:tmp dir 是临时路径,容器重启会丢 RSA key,JWT 无法解密旧 token

**结论**: 选 A。`Path("~/.sso/secrets/jwt_private.pem")` 在 Python pathlib 中通过 `.expanduser()` 自动 expand (Python 3.x 支持)。jwt_utils.py:91 调 `private_path.parent.mkdir(parents=True, exist_ok=True)` 时 `private_path` 是 `Path` 对象,`~` 已 expand (因为 `Path("~")` 在 `__new__` 时调 `os.path.expanduser`)。

### D2: 验证方法

**Context**: 修后必须验证 sso-1 healthcheck 真起。

**选项**:
- **A (已选)**: `docker compose -f docker-compose.yml -f docker-compose-dev.yml up -d` + 等 30s + `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` 期望 `(healthy)` + `docker exec chatbiz-sso-1 python -c "urllib.urlopen('http://127.0.0.1:8007/healthz').status"` 期望 `200`
- B: 只跑 unit test (sso cov 已有 100%) — 拒绝理由:不验容器 runtime,只验代码不验集成

**结论**: 选 A。

## Risks / Trade-offs

- **Risk 1 (低)**: `Path("~/.sso/secrets/jwt_private.pem")` 在某些 Python 版本下不自动 expand `~` — 实测 Python 3.12 `Path("~").expanduser() == PosixPath('/home/chatbiz-sso')`,`Path("~/foo") == PosixPath('/home/chatbiz-sso/foo')`,所以 OK。**但**:`jwt_utils.py:91` 用 `private_path.parent.mkdir(parents=True, exist_ok=True)`,`private_path` 是 `Path` 对象,`Path` 构造时会自动调 `os.path.expanduser`? — 实际不是,只在 `.expanduser()` 调时 expand。需要在 jwt_utils.py 或 lifespan.py 显式调 `.expanduser()`。**修正: lifespan.py:60-61 改用 `Path(os.getenv("JWT_PRIVATE_KEY_PATH", "~/.sso/secrets/jwt_private.pem")).expanduser()`,加 `.expanduser()` 调用**
- **Risk 2 (低)**: `os.path.expanduser` 在 `os.getenv` 之前或之后? — 实际 `os.getenv` 返回 str,然后 `Path(...)` 构造,`Path` 构造**不**自动 expand `~`。所以**必须显式调 `.expanduser()`**,否则 jwt_utils.py:91 拿到的 `private_path` 还是 `~/...`,`mkdir` 找 home dir 时可能 fail
- **Risk 3 (低)**: `chatbiz-sso` 用户的 `$HOME` 不一定是 `/home/chatbiz-sso` — `useradd --create-home --uid 10001` 默认 `$HOME=/home/chatbiz-sso`,Dockerfile line 34 已配。**环境变量 `$HOME` 在 USER chatbiz-sso 切换后保持 `/home/chatbiz-sso`**。OK

## Migration Plan

| # | Step | 产物 |
|---|---|---|
| 1 | 改 lifespan.py:60-61,加 `.expanduser()` | 1 file, 2 line edits (default 字符串 + 调 `.expanduser()`) |
| 2 | `git diff services/sso/app/lifespan.py` 验证 2 处改 | 4 lines diff (2 -, 2 +) |
| 3 | commit | 1 commit |
| 4 | 重建 sso image | `chatbiz/sso:dev` |
| 5 | `docker compose ... up -d` 跑 30s, 期望 sso-1 (healthy) | 端到端验证 |

**Rollback**: 任何步骤失败 → `git revert` 已 push 的 commits。

## Verification

| # | 验证项 | 命令 | 期望 |
|---|---|---|---|
| V1 | lifespan.py 改 2 行 | `git diff services/sso/app/lifespan.py` | 4 lines diff |
| V2 | lifespan.py 默认值含 `~/.sso/secrets/` | `grep "JWT_PRIVATE_KEY_PATH" services/sso/app/lifespan.py` | 输出含 `~/.sso/secrets/jwt_private.pem` |
| V3 | `.expanduser()` 调 | `grep "\.expanduser()" services/sso/app/lifespan.py` | 至少 1 行输出 |
| V4 | sso-1 (healthy) | `docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"` | `(healthy)` |
| V5 | sso-1 /healthz 端点 200 | `docker exec chatbiz-sso-1 python -c "urllib.urlopen('http://127.0.0.1:8007/healthz').status"` | `200` |
| V6 | chatbiz-web 3-gate 解锁 | `docker ps --filter name=chatbiz-web --format "{{.Status}}"` | `(healthy)` |

## Open Questions

无。trivial 2-line Python fix,无 Open Questions 段。如果 V5/V6 失败,需要回到 D1 重新分析(可能 `Path("~")` 在 `pathlib` 中需要显式 `.expanduser()` 调用才能 expand,Plan 已 Surface 在 Risk 1+2)。

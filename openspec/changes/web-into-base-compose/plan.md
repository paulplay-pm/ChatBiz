# web-into-base-compose Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the `chatbiz-web` (currently `web` short-key) unified SPA container from dev-only `docker-compose-dev.yml` to a first-class service in base `docker-compose.yml`, with the `web/Dockerfile` rewritten as a multi-stage image, and dev compose using `extends:` to pull and override the base.

**Architecture:** Three coordinated file changes. (1) `web/Dockerfile` becomes a two-stage image: `node:20-alpine` builder that runs `pnpm install --frozen-lockfile` + 3 `vite build` invocations, then `nginx:1.27-alpine` runtime that copies the three `dist/` directories + `nginx.conf`. (2) `infrastructure/docker-compose.yml` gains a `chatbiz-web:` service block (full `chatbiz-` prefix per `CLAUDE.md` mandatory convention; service key matches `chatbiz-postgres` / `chatbiz-redis` / `chatbiz-mcp` pattern) with explicit `container_name`, `build: { context: ../web }`, `image: chatbiz/web:dev`, `ports: ["5173:80"]`, `depends_on` on the three nginx upstreams with `condition: service_healthy`, and a `healthcheck` against `http://127.0.0.1:80/health`. (3) `infrastructure/docker-compose-dev.yml` rewrites the existing `web` block to `extends:` the base `chatbiz-web` block, re-declares `container_name: chatbiz-web` (for dev-namespace lint visibility) + `image: chatbiz/web:dev`, and bind-mounts `../web:/app` for live source reload.

**Tech Stack:** Docker Compose v2.20+ (multi-stage Dockerfile, `condition: service_healthy`, `extends:`), Node 20 (pnpm + Vite 5/6), nginx 1.27 (SPA serve + upstream proxy), shell `bash 4+` (macOS BSD awk compatible) for `tools/check-compose-naming.sh`.

**Worktree:** This plan MUST be executed inside `/Users/paulwang/work/ChatBiz/.worktrees/web-into-base-compose` (branch `worktree-web-into-base-compose`). All paths below are relative to the worktree root.

---

## File Structure (locked by this plan)

| File | Action | Responsibility |
|---|---|---|
| `web/Dockerfile` | **Modify** (rewrite as 2 stages) | Container build: pnpm install + 3 vite build → nginx runtime with dist + nginx.conf |
| `infrastructure/docker-compose.yml` | **Modify** (insert `chatbiz-web:` block before `workflow-engine:`) | Base compose registry for chatbiz-web service, depends_on 3 upstreams |
| `infrastructure/docker-compose-dev.yml` | **Modify** (replace `web:` block with `extends:` form) | Dev override: bind mount `../web:/app` + named `web-node-modules` volume |
| `openspec/changes/web-into-base-compose/{proposal,design,specs,tasks,plan}.md` | Already committed in `281e040` | Spec artifacts (no further changes in apply phase) |
| `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/retrospective.md` | **Create** at end | 5-followup retrospective per existing pattern |

No new source files in `services/`. No Python changes. No CI workflow changes.

---

## Task 1: Rewrite `web/Dockerfile` as multi-stage

**Files:**
- Modify: `web/Dockerfile` (full rewrite)

- [ ] **Step 1: Replace `web/Dockerfile` with the 2-stage version below**

Write this exact content to `web/Dockerfile`:

```dockerfile
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
```

- [ ] **Step 2: Verify the rewrite (V1)**

Run:
```bash
head -25 web/Dockerfile
```

Expected: first 25 lines contain both `FROM node:20-alpine AS builder` and `FROM nginx:1.27-alpine AS runtime` (or evidence of the second `FROM` further down). If only the builder stage is visible in head -25, that's OK — confirm the second `FROM` exists with `grep -n "FROM nginx" web/Dockerfile` showing two `FROM` lines total.

- [ ] **Step 3: Verify builder → runtime COPY linkage**

Run:
```bash
grep -E "^FROM|COPY --from=builder" web/Dockerfile
```

Expected: 2 `FROM` lines (`node:20-alpine AS builder` + `nginx:1.27-alpine AS runtime`) + at least 4 `COPY --from=builder` lines (portal/dist + canvas/dist + admin/dist + nginx.conf; index.html may also be copied).

- [ ] **Step 4: Commit Dockerfile rewrite**

```bash
git add web/Dockerfile
git commit -m "refactor(web): rewrite Dockerfile as multi-stage (node builder + nginx runtime)"
```

---

## Task 2: Insert `chatbiz-web:` service in base compose

**Files:**
- Modify: `infrastructure/docker-compose.yml` (insert new block between `mcp:` and `workflow-engine:`)

- [ ] **Step 1: Find the insertion point in base compose**

Run:
```bash
grep -n "^  mcp:\|^  workflow-engine:\|^  chatbiz-web:" infrastructure/docker-compose.yml
```

Expected: line numbers for `mcp:` and `workflow-engine:` are printed, and `chatbiz-web:` returns no match. Save the line number where `workflow-engine:` starts (call it `WF_LINE`) — you'll insert the new block immediately before it.

- [ ] **Step 2: Insert the `chatbiz-web:` block**

The block to insert (one blank line above and below, matching the style of the surrounding service blocks):

```yaml

  # ---------------------------------------------------------------------------
  # Web Frontend — unified SPA runtime (single-port nginx, all 5 sub-apps)
  # 多阶段构建见 web/Dockerfile (node:20-alpine builder + nginx:1.27-alpine runtime).
  # 路径分发见 web/nginx.conf;依赖 3 个 nginx upstream 等健康后起来。
  # ---------------------------------------------------------------------------
  chatbiz-web:
    build:
      context: ../web
      dockerfile: Dockerfile
    image: chatbiz/web:dev
    container_name: chatbiz-web
    restart: unless-stopped
    ports:
      - "5173:80"
    depends_on:
      workflow-engine:
        condition: service_healthy
      mcp:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://127.0.0.1:80/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 5s
```

Use `Edit` (or your editor) to insert this block immediately before the `  workflow-engine:` line. Keep the leading two-space indentation matching the other service blocks.

- [ ] **Step 3: Verify (V2) — `chatbiz-web` shows up in service list**

Run:
```bash
docker compose -f infrastructure/docker-compose.yml config --services 2>&1 | grep chatbiz-web
```

Expected: prints the single line `chatbiz-web` and exits 0. If docker compose complains about a parse error first, fix the YAML indentation before continuing.

- [ ] **Step 4: Verify (V3) — block structure is correct**

Run:
```bash
docker compose -f infrastructure/docker-compose.yml config 2>&1 | grep -A 25 "^  chatbiz-web:" | head -25
```

Expected: 25-line window containing (in this order) `container_name: chatbiz-web`, `build:`, `image: chatbiz/web:dev`, `ports:`, and `depends_on:` with `workflow-engine` and `mcp` (the base compose service keys resolving to containers `chatbiz-workflow-engine` and `chatbiz-mcp` at runtime) — both with `condition: service_healthy`. The third `chatbiz-sso` gate is added by the dev compose overlay in Task 3.

- [ ] **Step 5: Commit base compose block**

```bash
git add infrastructure/docker-compose.yml
git commit -m "feat(infrastructure): register chatbiz-web in base compose with 3 upstream health gates"
```

---

## Task 3: Rewrite dev compose `web:` block as `extends:`

**Files:**
- Modify: `infrastructure/docker-compose-dev.yml` (replace the existing `web:` block at lines 174-184)

- [ ] **Step 1: Locate the existing `web:` block in dev compose**

Run:
```bash
grep -n "^  web:\|^  chatbiz-web:" infrastructure/docker-compose-dev.yml
```

Expected: `web:` matches at line 174; `chatbiz-web:` returns no match. Note the range — the existing `web:` block spans lines 174-184 (10 lines including the `ports:` line and trailing blank).

- [ ] **Step 2: Replace the `web:` block with the `extends:` form**

Delete lines 174-184 (the entire current `web:` block including its blank line below) and insert this replacement in its place:

```yaml
  web:
    extends:
      file: docker-compose.yml
      service: chatbiz-web
    # Re-declare container_name so dev-namespace lint visibility holds
    # (V6b FU-3 rule 2, see tools/check-compose-naming.sh).
    container_name: chatbiz-web
    image: chatbiz/web:dev
    # Re-declare depends_on to ADD chatbiz-sso as the 3rd health gate
    # (base compose only has workflow-engine + mcp; chatbiz-sso is a
    # dev-only service that becomes available when the dev overlay is
    # active). Compose `extends:` does NOT merge lists, so the dev block
    # must redeclare the full depends_on list.
    depends_on:
      chatbiz-sso:
        condition: service_healthy
      workflow-engine:
        condition: service_healthy
      mcp:
        condition: service_healthy
    # Bind-mount the source for live reload of nginx config + dist rebuilds
    # triggered by `docker compose build chatbiz-web` after source edits.
    volumes:
      - ../web:/app
      - web-node-modules:/app/node_modules
```

Use `Edit` (or your editor). The replacement must occupy the same indentation column as the deleted block (2-space leading indent for the `web:` key).

- [ ] **Step 3: Verify (V4) — `extends:` references base**

Run:
```bash
grep -A 6 "^  web:" infrastructure/docker-compose-dev.yml
```

Expected: 6-line window containing `extends:`, `file: docker-compose.yml`, `service: chatbiz-web`, and `depends_on:` with `chatbiz-sso` + `workflow-engine` + `mcp` (3 service health gate re-declared in dev overlay).

- [ ] **Step 4: Verify the named volume still exists in top-level `volumes:`**

Run:
```bash
grep -A 1 "^  web-node-modules:" infrastructure/docker-compose-dev.yml
```

Expected: `name: chatbiz-web-node-modules` (preserved from current line 257-258). If this line is missing, add the following block to the top-level `volumes:` section (anywhere after `pycache-workflow-engine:`):

```yaml
  web-node-modules:
    name: chatbiz-web-node-modules
```

- [ ] **Step 5: Commit dev compose rewrite**

```bash
git add infrastructure/docker-compose-dev.yml
git commit -m "refactor(infrastructure): dev compose web block uses extends: chatbiz-web"
```

---

## Task 4: Lint + e2e verification

**Files:** none modified; verification only.

- [ ] **Step 1: Run the compose-naming lint (V5)**

Run:
```bash
bash tools/check-compose-naming.sh
```

Expected: exit 0, output ends with `OK: 0 error(s), 0 warning(s)`. If exit 1, read the FAIL message — most likely cause is the dev compose `chatbiz-web` `extends:` block missing the explicit `container_name` re-declaration (Task 3.2). Fix and re-run.

- [ ] **Step 2: Build the chatbiz-web image (V6)**

Run:
```bash
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml build chatbiz-web 2>&1 | tail -20
```

Expected: exit 0, last 20 lines show a successful `naming to docker.io/chatbiz/web:dev` (or `chatbiz-web` tag) plus the final layers exported. If the build fails in the `pnpm install` step, check that `web/pnpm-lock.yaml` exists and the `web/portal|canvas|admin/package.json` paths match the Dockerfile `COPY` lines (Task 1.1).

- [ ] **Step 3: Confirm the image exists**

Run:
```bash
docker images chatbiz/web:dev --format "{{.Repository}}:{{.Tag}} {{.Size}}"
```

Expected: prints `chatbiz/web:dev <size>` (size is typically 50-150 MB for the nginx runtime stage).

- [ ] **Step 4: Start the full dev stack (V7)**

Run (this starts every service defined in the dev compose overlay):
```bash
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d 2>&1 | tail -30
sleep 30
docker ps --filter name=chatbiz-web --format "table {{.Names}}\t{{.Status}}"
```

Expected: `chatbiz-web` row shows status `(healthy)` within 30s of `up -d`. If status is `starting` or `unhealthy`, wait 30s more and re-check; if still unhealthy, inspect logs:
```bash
docker logs chatbiz-web --tail 50
```

- [ ] **Step 5: Hit the nginx `/health` endpoint (V8)**

Run:
```bash
curl -fsS http://localhost:5173/health
```

Expected: prints `OK` and exits 0. If you see 502/503, nginx hasn't started yet — re-run after another 10s.

- [ ] **Step 6: Hit the SSO upstream proxy (V9)**

Run (requires `chatbiz-sso` to also be healthy):
```bash
curl -fsS http://localhost:5173/api/auth/sso/jwks.json
```

Expected: prints a JSON body with `keys` array (the SSO JWKS document). If you see 502, the `chatbiz-sso` upstream is not healthy — check `docker ps --filter name=chatbiz-sso` and wait for its healthcheck.

- [ ] **Step 7: Hit the workflow-engine upstream proxy (V10)**

Run (requires `workflow-engine` to also be healthy):
```bash
curl -fsS http://localhost:5173/workflows/healthz
```

Expected: prints body and exits 0 (HTTP 200). If you see 502, the `workflow-engine` upstream is not healthy — check `docker ps --filter name=chatbiz-workflow-engine` and wait for its healthcheck.

---

## Task 5: openspec archive + commit + push + retrospective

**Files:**
- Modify: nothing
- Create: `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/retrospective.md`

- [ ] **Step 1: Archive the change**

Run:
```bash
openspec archive --change web-into-base-compose --yes 2>&1 | tail -10
```

Expected: exit 0, output confirms the change is archived into `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/`. (Per project convention, `archive` is a one-shot commit + move. The repo-wide convention from `CLAUDE.md` is "chore(openspec): archive <name>" as the second commit message.)

- [ ] **Step 2: Verify the archive commit + active change removal**

Run:
```bash
git log --oneline -5
ls openspec/changes/web-into-base-compose 2>&1
```

Expected:
- `git log` shows 4 new commits in order: Task 1.4 Dockerfile rewrite, Task 2.5 base compose insert, Task 3.5 dev compose extends, then `chore(openspec): archive chatbiz-web-into-base-compose` (or the equivalent `web-into-base-compose` per openspec's default message).
- The second `ls` returns "No such file or directory" — the active change directory is gone, the archive copy lives under `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/`.

- [ ] **Step 3: Push the branch to remote**

Run:
```bash
git push origin worktree-web-into-base-compose 2>&1 | tail -5
```

Expected: `* [new branch] worktree-web-into-base-compose -> worktree-web-into-base-compose` and exit 0.

- [ ] **Step 4: Write the retrospective**

Create the file `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/retrospective.md` with the following structure (substitute the actual values; do not leave any `[FILL IN]` placeholder):

```markdown
# Retrospective: chatbiz-web-into-base-compose

## 总结

本 change 在 1 个 session 内跑完完整 superpowers-bridge 流程
(brainstorm → proposal → design → specs → tasks → plan → apply → archive)。
N 个 commit push 到 main。

### 实际耗时

| 阶段 | 预期 | 实际 | 偏差原因 |
|---|---|---|---|
| Brainstorm + Q1-Q4 | 0.5h | 0.5h | AskUserQuestion 4 round 收口 scope,符合 |
| Proposal + Design | 0.5h | 0.5h | 1 页 A4 |
| Specs (5 requirements) | 0.5h | 0.5h | 写起来顺 |
| Tasks + Plan | 0.5h | 0.5h | 11 步 micro-step 拆好 |
| Apply (4 commits) | 1.0h | [FILL IN]h | [FILL IN 偏差原因] |
| Verify (V1-V10) | 0.5h | [FILL IN]h | [FILL IN 偏差原因] |
| Archive + commit + push | 0.1h | 0.1h | 顺 |

## 学到了什么

### ✅ 决策正确的部分
1. ...
2. ...

### ⚠️ 决策需要调整的部分
1. ...

## 验收条件 vs 实际(design.md Verification 段)

| 验收条件 | 状态 | 证据 |
|---|---|---|
| V1 Dockerfile 多阶段 | ✅ / ❌ | `head -25 web/Dockerfile` 输出 |
| V2 base compose 列 chatbiz-web | ✅ / ❌ | ... |
| V3 base compose 段格式 | ✅ / ❌ | ... |
| V4 dev compose 段 extends | ✅ / ❌ | ... |
| V5 命名 lint PASS | ✅ / ❌ | ... |
| V6 容器 build | ✅ / ❌ | ... |
| V7 容器 up + healthy | ✅ / ❌ | ... |
| V8 nginx /health 端点 | ✅ / ❌ | ... |
| V9 sso upstream proxy | ✅ / ❌ | ... |
| V10 workflow upstream proxy | ✅ / ❌ | ... |

## 5 followup 行动
1. ...
2. ...
3. ...
4. ...
5. ...

## 状态
**已 archive** — `openspec/changes/archive/2026-06-16-chatbiz-web-into-base-compose/`。
N commits pushed.
```

- [ ] **Step 5: Clean up the worktree**

Run:
```bash
git worktree remove /Users/paulwang/work/ChatBiz/.worktrees/web-into-base-compose
git branch -d worktree-web-into-base-compose
git worktree list
```

Expected:
- `worktree remove` exits 0 and prints nothing (or a success message).
- `git branch -d` exits 0 (the branch is fully merged because Task 5.1's archive commit is on it).
- `git worktree list` shows only `/Users/paulwang/work/ChatBiz  <sha> [main]` — the worktree entry is gone.

- [ ] **Step 6: Final sanity check on main**

Run:
```bash
cd /Users/paulwang/work/ChatBiz
git log --oneline -10
git status -s
```

Expected:
- `git log` shows the 4-5 new commits at the top (3 apply commits + 1 archive + maybe 1 retro).
- `git status -s` is empty — main is clean.

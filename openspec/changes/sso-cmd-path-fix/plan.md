# sso-cmd-path-fix Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. This is a trivial 2-line Dockerfile fix + verify. Execute inline (no subagent dispatch needed).

**Goal:** Fix `services/sso/Dockerfile` so the source is installed at `/app/app/` instead of `/home/sso/app/`, allowing the `uvicorn app.main:app` CMD to resolve the FastAPI `app` package.

**Architecture:** 2-line Dockerfile change. `WORKDIR` and the `COPY` target both move from `/home/sso` to `/app`. Everything else (python packages, non-root user, healthcheck, CMD args) stays untouched.

**Tech Stack:** bash + sed/Edit, docker compose v2.20+, docker build.

**Worktree:** `/Users/paulwang/work/ChatBiz/.worktrees/sso-cmd-path-fix` (branch `worktree-sso-cmd-path-fix`).

---

## Task 1: Edit `services/sso/Dockerfile`

**Files:**
- Modify: `services/sso/Dockerfile` (2 line edits: line 36 + line 41)

- [ ] **Step 1: Read current Dockerfile line 36 + 41**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/sso-cmd-path-fix
sed -n '34,42p' services/sso/Dockerfile
```

Expected output (current state, before edit):
```
USER chatbiz-sso would normally go here; we're after the WORKDIR + COPY lines.

WORKDIR /home/sso

# Copy the pip user-site (built in the builder stage) into the new user's
# $HOME, then chown the working tree to the non-root user.
COPY --from=builder /root/.local /home/chatbiz-sso/.local
COPY --chown=chatbiz-sso:chatbiz-sso . /home/sso
```

(Approximate; actual content matches `services/sso/Dockerfile:36-41`.)

- [ ] **Step 2: Edit line 36 — `WORKDIR /home/sso` → `WORKDIR /app`**

Use the Edit tool to change:
```diff
-WORKDIR /home/sso
+WORKDIR /app
```

- [ ] **Step 3: Edit line 41 — `COPY --chown=... . /home/sso` → `COPY --chown=... . /app`**

Use the Edit tool to change:
```diff
-COPY --chown=chatbiz-sso:chatbiz-sso . /home/sso
+COPY --chown=chatbiz-sso:chatbiz-sso . /app
```

(Note: line 40 `COPY --from=builder /root/.local /home/chatbiz-sso/.local` stays UNTOUCHED — it copies python packages to the non-root user's $HOME, which is independent of WORKDIR.)

- [ ] **Step 4: Verify diff scope (V1)**

```bash
git diff services/sso/Dockerfile
```

Expected: 4 lines changed (2 deletions + 2 insertions), all on lines 36 and 41.

- [ ] **Step 5: Verify WORKDIR + COPY content (V1.5 + V1.6)**

```bash
grep -E "^WORKDIR" services/sso/Dockerfile
grep -E "^COPY.*\.$" services/sso/Dockerfile
```

Expected:
- First command prints `WORKDIR /app`
- Second command prints `COPY --chown=chatbiz-sso:chatbiz-sso . /app`
- Neither contains `/home/sso` (other than the `COPY --from=builder ... /home/chatbiz-sso/.local` on line 40 which is intentionally untouched)

- [ ] **Step 6: Commit the fix**

```bash
git add services/sso/Dockerfile
git commit -m "fix(sso): align WORKDIR + COPY target to /app so uvicorn can find app/main.py"
```

## Task 2: Rebuild sso image + end-to-end docker compose verification

**Files:** none modified (verification only).

- [ ] **Step 1: Rebuild the sso image (V2)**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/sso-cmd-path-fix
docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso 2>&1 | tail -15
```

Expected: exit 0, last 15 lines show successful build (`naming to docker.io/chatbiz/sso:dev` + final layer exports).

- [ ] **Step 2: Verify image rebuilt**

```bash
docker images chatbiz/sso:dev --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}"
```

Expected: prints `chatbiz/sso:dev` with a `CreatedAt` timestamp within the last few minutes.

- [ ] **Step 3: Bring up the full dev stack**

```bash
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d 2>&1 | tail -10
sleep 30
```

Expected: compose up runs to completion, sso-1 transitions to `Up` then `(healthy)` within 30s. mcp + workflow-engine transition to `(healthy)` after sso-1 healthcheck passes (their 3-gate depends_on requires sso to be healthy).

- [ ] **Step 4: Verify sso-1 healthy (V3)**

```bash
docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"
```

Expected: prints `(healthy)`. If `Exited (2)`, the fix didn't apply — check `docker logs chatbiz-sso-1 --tail 30`.

- [ ] **Step 5: Verify cascade — mcp + workflow-engine healthy (V4)**

```bash
docker ps --filter name=chatbiz-mcp --filter name=chatbiz-workflow-engine --format "{{.Names}}: {{.Status}}"
```

Expected: 2 lines, each ending with `(healthy)`.

- [ ] **Step 6: Verify sso-1 healthcheck endpoint returns 200 (V5)**

```bash
docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"
```

Expected: prints `200` and exits 0.

## Task 3: openspec archive + merge + push + retrospective

**Files:**
- Create: `openspec/changes/archive/2026-06-16-sso-cmd-path-fix/retrospective.md`

- [ ] **Step 1: Archive the change**

```bash
openspec archive sso-cmd-path-fix --yes 2>&1 | tail -5
git status -s
```

Expected: change moved to `openspec/changes/archive/2026-06-16-sso-cmd-path-fix/`, working tree shows renames + 1 new file in `openspec/specs/sso-cmd-path-fix/spec.md`.

- [ ] **Step 2: Commit archive + spec delta**

```bash
git add -A
git commit -m "chore(openspec): archive sso-cmd-path-fix + apply sso-cmd-path-fix spec delta"
```

- [ ] **Step 3: Merge to main and push**

```bash
cd /Users/paulwang/work/ChatBiz
git merge --no-ff worktree-sso-cmd-path-fix -m "Merge branch 'worktree-sso-cmd-path-fix'

2-line Dockerfile fix: WORKDIR /home/sso → /app + COPY target /home/sso → /app.
Unblocks chatbiz-sso-1 container (was Exited (2) due to uvicorn 'app/main.py not found')
and cascades to unblock chatbiz-mcp + chatbiz-workflow-engine via the dev compose
chatbiz-web 3-gate depends_on: sso: service_healthy chain. Followup to
sso-real-impl (2026-06-14) which wrote the Python source but missed aligning
the Dockerfile WORKDIR."
git push origin main
```

- [ ] **Step 4: Write retrospective**

Create `openspec/changes/archive/2026-06-16-sso-cmd-path-fix/retrospective.md` following the 5-section structure (summary, 实际耗时, 学到了什么, 验收条件 vs 实际, 5 followup 行动, 状态).

```bash
git add openspec/changes/archive/2026-06-16-sso-cmd-path-fix/retrospective.md
git commit -m "docs(openspec): retrospective for sso-cmd-path-fix"
git push origin main
```

- [ ] **Step 5: Clean up worktree + branches**

```bash
git worktree remove /Users/paulwang/work/ChatBiz/.worktrees/sso-cmd-path-fix
git branch -d worktree-sso-cmd-path-fix
git push origin --delete worktree-sso-cmd-path-fix
git worktree list
```

Expected: worktree removed, local + remote branch deleted, `git worktree list` shows only main.

- [ ] **Step 6: Final main sanity check**

```bash
git log --oneline -5
git status -s
```

Expected: 3 new commits at top (fix + archive + retro), working tree clean.

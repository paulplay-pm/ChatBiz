# sso-healthz-route-fix Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. This is a small fix moving one handler + correcting one context manager call. Execute inline.

**Goal:** Fix the 2 pre-existing bugs in sso-real-impl (Layer 4a + 4b) so the `chatbiz-sso-1` container's `/healthz` endpoint returns HTTP 200, allowing the dev compose `chatbiz-web` 3-gate to fully unlock and Web SSO to work end-to-end.

**Architecture:** Move the `/healthz` route from `routers/sso.py` (where it's incorrectly placed under the `APIRouter(prefix="/api/v1/auth/sso")` prefix) to `main.py` (where it's directly registered via `@app.get("/healthz")` with no prefix). The handler implementation also gets corrected: use `async with request.app.state.db_sessionmaker() as session:` (where `db_sessionmaker` is the `async_sessionmaker` used as a context manager) instead of the buggy `db = db_sessionmaker(); async with db() as session:` (which tries to call the returned `AsyncSession` as a function).

**Tech Stack:** Python 3.12 + FastAPI lifespan + SQLAlchemy 2.0 async (`async_sessionmaker` context manager), docker compose v2.20+, docker build.

**Worktree:** `/Users/paulwang/work/ChatBiz/.worktrees/sso-healthz-route-fix` (branch `worktree-sso-healthz-route-fix`).

---

## Task 1: Edit `services/sso/app/main.py` and `services/sso/app/routers/sso.py`

**Files:**
- Modify: `services/sso/app/main.py` (add ~15 lines: import + healthz decorator + handler)
- Modify: `services/sso/app/routers/sso.py` (delete ~17 lines: the entire `# --- /healthz ---` block)

- [ ] **Step 1: Read current state**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/sso-healthz-route-fix
grep -n "include_router\|/healthz\|async def healthz" services/sso/app/main.py
echo "---"
grep -n "healthz\|@router.get" services/sso/app/routers/sso.py
```

Expected:
- `main.py` shows one `include_router(sso_router.router)` line; no `healthz` references
- `routers/sso.py` shows one `@router.get("/healthz")` line and the `async def healthz(request: Request):` handler

- [ ] **Step 2: Add `/healthz` route to `main.py`**

Edit `services/sso/app/main.py`. First, add a new import at the top of the file (after the existing `from .lifespan import lifespan` line):

```python
from sqlalchemy import text
```

Then, in `create_app()` (after `app = FastAPI(...)` and the CORS middleware setup, **before** `app.include_router(sso_router.router)`), add:

```python
    # /healthz — system-level healthcheck (no APIRouter prefix; must be reachable
    # at root path so services/sso/Dockerfile HEALTHCHECK can call it).
    @app.get("/healthz")
    async def healthz(request: Request):
        try:
            async with request.app.state.db_sessionmaker() as session:
                await session.execute(text("SELECT 1"))
            return {"status": "healthy"}
        except Exception as e:  # noqa: BLE001
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "error": str(e)},
            )
```

(Note: the existing `sso/routers/sso.py:healthz` body is a near-exact match for this new body — just the path registration changes.)

- [ ] **Step 3: Delete `/healthz` block from `routers/sso.py`**

Edit `services/sso/app/routers/sso.py`. Delete the entire `# --- /healthz ---` block. It looks like (approximately, depending on whitespace):

```python
# --- /healthz ---
@router.get("/healthz")
async def healthz(request: Request):
    db = request.app.state.db_sessionmaker()
    try:
        async with db() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "healthy"}
    except Exception as e:  # noqa: BLE001
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)},
        )
```

(The exact line numbers and indentation can be confirmed with the grep from Step 1.)

Also: if `routers/sso.py` no longer uses `text` from sqlalchemy after deleting the healthz block, you may optionally remove the `from sqlalchemy import text` import. But this is a followup cleanup — not required for this change.

- [ ] **Step 4: Verify V1 (main.py has @app.get("/healthz"))**

```bash
grep '@app.get("/healthz")' services/sso/app/main.py
```

Expected: prints one line (the new decorator).

- [ ] **Step 5: Verify V2 (healthz handler uses session.execute inside async with)**

```bash
grep -A 3 "async with" services/sso/app/main.py
```

Expected: shows the `async with request.app.state.db_sessionmaker() as session:` block followed by `await session.execute(text("SELECT 1"))`.

- [ ] **Step 6: Verify V3 (routers/sso.py no longer mentions healthz)**

```bash
grep -c "healthz" services/sso/app/routers/sso.py
```

Expected: prints `0`.

- [ ] **Step 7: Verify V4 (diff scope)**

```bash
git diff --stat services/sso/app/
```

Expected: 2 files changed. `main.py` should have ~15 lines added, `routers/sso.py` should have ~17 lines removed (net change should be small or negative).

- [ ] **Step 8: Commit**

```bash
git add services/sso/app/main.py services/sso/app/routers/sso.py
git commit -m "fix(sso): move /healthz to main.py (no APIRouter prefix) + use async_sessionmaker as context manager"
```

## Task 2: Rebuild sso image + end-to-end docker compose verification

**Files:** none modified (verification only).

- [ ] **Step 1: Rebuild the sso image**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/sso-healthz-route-fix
docker build -t chatbiz/sso:dev -f services/sso/Dockerfile services/sso 2>&1 | tail -10
```

Expected: exit 0, last lines show successful build (`naming to docker.io/chatbiz/sso:dev` + final layer exports).

- [ ] **Step 2: Verify image rebuilt**

```bash
docker images chatbiz/sso:dev --format "{{.Repository}}:{{.Tag}} {{.CreatedAt}}"
```

Expected: prints `chatbiz/sso:dev` with a fresh `CreatedAt` timestamp (within last few minutes).

- [ ] **Step 3: Bring up the full dev stack**

```bash
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d 2>&1 | tail -10
sleep 30
```

Expected: sso-1 transitions from `Up (unhealthy)` (with old image) → `Recreated` → `Up (healthy)` (with new image + new healthz route that succeeds). chatbiz-web 3-gate unlocks (it was Created before).

- [ ] **Step 4: Verify sso-1 healthy (V5)**

```bash
docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"
```

Expected: prints `(healthy)`. If `Up (unhealthy)`, the fix didn't apply — check `docker logs chatbiz-sso-1 --tail 30` for the new error.

- [ ] **Step 5: Verify sso-1 /healthz returns 200 (V6)**

```bash
docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"
```

Expected: prints `200` and exits 0.

- [ ] **Step 6: Verify chatbiz-web 3-gate unlocked (V7)**

```bash
docker ps --filter name=chatbiz-web --format "{{.Status}}"
```

Expected: prints `(healthy)`.

- [ ] **Step 7: Verify Web SSO end-to-end (V8)**

```bash
curl -fsS http://localhost:5173/api/auth/sso/jwks.json | head -c 200
```

Expected: prints a JSON body starting with `{"keys":` (or similar JWKS structure), exit 0. If 502, the nginx upstream for chatbiz-sso isn't routing correctly.

## Task 3: openspec archive + merge + push + retrospective

**Files:**
- Create: `openspec/changes/archive/2026-06-16-sso-healthz-route-fix/retrospective.md`

- [ ] **Step 1: Archive the change**

```bash
openspec archive sso-healthz-route-fix --yes 2>&1 | tail -5
git status -s
```

Expected: change moved to `openspec/changes/archive/2026-06-16-sso-healthz-route-fix/`, working tree shows renames + 1 new file in `openspec/specs/sso-healthz-route-fix/spec.md`.

- [ ] **Step 2: Commit archive + spec delta**

```bash
git add -A
git commit -m "chore(openspec): archive sso-healthz-route-fix + apply sso-healthz-route-fix spec delta"
```

- [ ] **Step 3: Merge to main and push**

```bash
cd /Users/paulwang/work/ChatBiz
git merge --no-ff worktree-sso-healthz-route-fix -m "Merge branch 'worktree-sso-healthz-route-fix'

Move sso /healthz route from routers/sso.py (where it was incorrectly prefixed
under /api/v1/auth/sso by the APIRouter) to main.py (registered at root path
via @app.get). Also fix the handler to use async_sessionmaker as a context
manager directly (async with db_sessionmaker() as session:) instead of the
buggy db = db_sessionmaker(); async with db() as session: which tried to
call the returned AsyncSession. Unblocks chatbiz-sso-1 from Up (unhealthy)
to (healthy) and unlocks the dev compose chatbiz-web 3-gate depends_on:
sso: service_healthy chain. Followup to sso-secrets-path-fix (2026-06-16)
and sso-real-impl (2026-06-14)."
git push origin main
```

- [ ] **Step 4: Write retrospective**

Create `openspec/changes/archive/2026-06-16-sso-healthz-route-fix/retrospective.md` following the 5-section structure (summary, 实际耗时, 学到了什么, 验收条件 vs 实际, 5 followup 行动, 状态). Key points:
- Trivial 2-file move + 1-line context manager fix
- 0 deviations (plan matched implementation)
- V1-V8 all PASS on first try
- Layer 4a (APIRouter prefix) and Layer 4b (AsyncSession.call()) both fixed
- Web SSO end-to-end now works (curl /api/auth/sso/jwks.json returns 200)
- Lesson: when registering healthcheck routes, always use root path with no prefix; when using async_sessionmaker, use it directly as context manager without calling first

```bash
git add openspec/changes/archive/2026-06-16-sso-healthz-route-fix/retrospective.md
git commit -m "docs(openspec): retrospective for sso-healthz-route-fix"
git push origin main
```

- [ ] **Step 5: Clean up worktree + branches**

```bash
git worktree remove --force /Users/paulwang/work/ChatBiz/.worktrees/sso-healthz-route-fix
git branch -d worktree-sso-healthz-route-fix
git push origin --delete worktree-sso-healthz-route-fix
git worktree list
```

Expected: worktree removed, local + remote branch deleted, `git worktree list` shows only main.

- [ ] **Step 6: Final main sanity check**

```bash
git log --oneline -5
git status -s
```

Expected: 3 new commits at top (fix + archive + retro), working tree clean.

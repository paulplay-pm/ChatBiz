# sso-secrets-path-fix Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax. This is a trivial 2-line Python source fix + verify. Execute inline.

**Goal:** Change `services/sso/app/lifespan.py:60-61` so the default `JWT_PRIVATE_KEY_PATH` / `JWT_PUBLIC_KEY_PATH` resolves to a path the non-root `chatbiz-sso` user can write to (specifically `~/.sso/secrets/...` instead of cwd-relative `secrets/...`), allowing the FastAPI lifespan to complete RSA key generation and the sso container to reach `(healthy)`.

**Architecture:** 2-line Python source change. The `Path()` constructor now takes a home-relative path string and is followed by an explicit `.expanduser()` call so that `~` is resolved to `$HOME` (= `/home/chatbiz-sso` per `useradd --create-home` on Dockerfile line 34) before `jwt_utils.load_or_generate_keypair` does its `private_path.parent.mkdir()`.

**Tech Stack:** Python 3.12 pathlib (`Path.expanduser()`), docker compose v2.20+, docker build.

**Worktree:** `/Users/paulwang/work/ChatBiz/.worktrees/sso-secrets-path-fix` (branch `worktree-sso-secrets-path-fix`).

---

## Task 1: Edit `services/sso/app/lifespan.py`

**Files:**
- Modify: `services/sso/app/lifespan.py` (2 line edits: line 60 + line 61)

- [ ] **Step 1: Read current lifespan.py line 60-61**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/sso-secrets-path-fix
sed -n '58,62p' services/sso/app/lifespan.py
```

Expected output:
```
    # 4. RSA 私钥 load_or_generate
    private_path = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "secrets/jwt_private.pem"))
    public_path = Path(os.getenv("JWT_PUBLIC_KEY_PATH", "secrets/jwt_public.pem"))
```

- [ ] **Step 2: Edit line 60 — change default to home-relative + add `.expanduser()`**

Use the Edit tool to change:
```diff
-    private_path = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "secrets/jwt_private.pem"))
+    private_path = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "~/.sso/secrets/jwt_private.pem")).expanduser()
```

- [ ] **Step 3: Edit line 61 — same change for public key path**

Use the Edit tool to change:
```diff
-    public_path = Path(os.getenv("JWT_PUBLIC_KEY_PATH", "secrets/jwt_public.pem"))
+    public_path = Path(os.getenv("JWT_PUBLIC_KEY_PATH", "~/.sso/secrets/jwt_public.pem")).expanduser()
```

- [ ] **Step 4: Verify diff scope (V1)**

```bash
git diff services/sso/app/lifespan.py
```

Expected: 4 lines changed (2 deletions + 2 insertions), exactly on the two `Path(os.getenv(...))` lines.

- [ ] **Step 5: Verify content (V2 + V3)**

```bash
grep "JWT_PRIVATE_KEY_PATH" services/sso/app/lifespan.py
grep -E "expanduser" services/sso/app/lifespan.py
```

Expected:
- First command prints `private_path = Path(os.getenv("JWT_PRIVATE_KEY_PATH", "~/.sso/secrets/jwt_private.pem")).expanduser()` (and similar for public_path)
- Second command prints 2 lines, one for `private_path` and one for `public_path`, both with `.expanduser()`

- [ ] **Step 6: Commit the fix**

```bash
git add services/sso/app/lifespan.py
git commit -m "fix(sso): use ~/.sso/secrets/ default for JWT key paths so non-root user can write"
```

## Task 2: Rebuild sso image + end-to-end docker compose verification

**Files:** none modified (verification only).

- [ ] **Step 1: Rebuild the sso image**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/sso-secrets-path-fix
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

Expected: compose up runs to completion, sso-1 transitions from `Up (unhealthy)` (with old image) → `Recreated` → `Up (healthy)` (with new image + new default path that succeeds). chatbiz-web 3-gate unlocks.

- [ ] **Step 4: Verify sso-1 healthy (V4)**

```bash
docker ps --filter name=chatbiz-sso-1 --format "{{.Status}}"
```

Expected: prints `(healthy)`. If `Up (unhealthy)`, the fix didn't apply — check `docker logs chatbiz-sso-1 --tail 30`.

- [ ] **Step 5: Verify JWT key file created at home-relative path (V3-files)**

```bash
docker exec chatbiz-sso-1 ls /home/chatbiz-sso/.sso/secrets/jwt_private.pem
```

Expected: prints the full path `/home/chatbiz-sso/.sso/secrets/jwt_private.pem` (exit 0), proving the file was generated at the home-relative path.

- [ ] **Step 6: Verify sso-1 /healthz returns 200 (V5)**

```bash
docker exec chatbiz-sso-1 python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8007/healthz').status)"
```

Expected: prints `200` and exits 0.

- [ ] **Step 7: Verify chatbiz-web 3-gate unlocked (V6)**

```bash
docker ps --filter name=chatbiz-web --format "{{.Status}}"
```

Expected: prints `(healthy)`. If `Created` or `Up (unhealthy)`, the 3-gate isn't fully satisfied.

- [ ] **Step 8: Verify Web SSO end-to-end (V-end-to-end)**

```bash
curl -fsS http://localhost:5173/api/auth/sso/jwks.json | head -c 200
```

Expected: prints a JSON body starting with `{"keys":` (or similar JWKS structure), exit 0. If 502, the nginx upstream for chatbiz-sso isn't routing correctly.

## Task 3: openspec archive + merge + push + retrospective

**Files:**
- Create: `openspec/changes/archive/2026-06-16-sso-secrets-path-fix/retrospective.md`

- [ ] **Step 1: Archive the change**

```bash
openspec archive sso-secrets-path-fix --yes 2>&1 | tail -5
git status -s
```

Expected: change moved to `openspec/changes/archive/2026-06-16-sso-secrets-path-fix/`, working tree shows renames + 1 new file in `openspec/specs/sso-secrets-path-fix/spec.md`.

- [ ] **Step 2: Commit archive + spec delta**

```bash
git add -A
git commit -m "chore(openspec): archive sso-secrets-path-fix + apply sso-secrets-path-fix spec delta"
```

- [ ] **Step 3: Merge to main and push**

```bash
cd /Users/paulwang/work/ChatBiz
git merge --no-ff worktree-sso-secrets-path-fix -m "Merge branch 'worktree-sso-secrets-path-fix'

2-line Python source fix in services/sso/app/lifespan.py: change the default
JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH from cwd-relative 'secrets/...'
to home-relative '~/.sso/secrets/...' (with explicit .expanduser() call).
Unblocks chatbiz-sso-1 from 'Up (unhealthy)' to '(healthy)' and unlocks the
dev compose chatbiz-web 3-gate depends_on: sso: service_healthy chain.
Followup to sso-cmd-path-fix (2026-06-16) and sso-real-impl (2026-06-14)."
git push origin main
```

- [ ] **Step 4: Write retrospective**

Create `openspec/changes/archive/2026-06-16-sso-secrets-path-fix/retrospective.md` following the 5-section structure (summary, 实际耗时, 学到了什么, 验收条件 vs 实际, 5 followup 行动, 状态).

```bash
git add openspec/changes/archive/2026-06-16-sso-secrets-path-fix/retrospective.md
git commit -m "docs(openspec): retrospective for sso-secrets-path-fix"
git push origin main
```

- [ ] **Step 5: Clean up worktree + branches**

```bash
git worktree remove --force /Users/paulwang/work/ChatBiz/.worktrees/sso-secrets-path-fix
git branch -d worktree-sso-secrets-path-fix
git push origin --delete worktree-sso-secrets-path-fix
git worktree list
```

Expected: worktree removed, local + remote branch deleted, `git worktree list` shows only main.

- [ ] **Step 6: Final main sanity check**

```bash
git log --oneline -5
git status -s
```

Expected: 3 new commits at top (fix + archive + retro), working tree clean.

# fix-migrate-hostname Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. This plan is small enough (8 micro-steps, 1 commit) to execute inline without subagent dispatch.

**Goal:** Replace all 9 occurrences of `postgres:5432` with `chatbiz-postgres:5432` in `infrastructure/docker-compose.yml` so that the 4 one-shot `*-migrate` containers can resolve the database host via Docker Compose's internal DNS.

**Architecture:** One-line sed replacement in a single file. The change is a strict followup to `8c0df0b` (which renamed the service key but missed 9 internal env-var references). No new architecture, no new service, no new env var.

**Tech Stack:** bash + sed, docker compose v2.20+.

**Worktree:** `/Users/paulwang/work/ChatBiz/.worktrees/fix-migrate-hostname` (branch `worktree-fix-migrate-hostname`). All paths relative to worktree root.

---

## Task 1: Apply the sed replacement

**Files:**
- Modify: `infrastructure/docker-compose.yml` (9 line edits, 9 insertions, 9 deletions)

- [ ] **Step 1: Run the sed replacement**

```bash
cd /Users/paulwang/work/ChatBiz/.worktrees/fix-migrate-hostname
sed -i '' 's|@postgres:5432|@chatbiz-postgres:5432|g' infrastructure/docker-compose.yml
```

Expected: exit 0, no output. The `sed` flag is macOS-BSD-compatible (empty `''` after `-i`).

- [ ] **Step 2: Verify 0 occurrences of `postgres:5432` (V1)**

```bash
grep -c "postgres:5432" infrastructure/docker-compose.yml
```

Expected: prints `0` and exits 0.

- [ ] **Step 3: Verify 9 occurrences of `chatbiz-postgres:5432` (V2)**

```bash
grep -c "chatbiz-postgres:5432" infrastructure/docker-compose.yml
```

Expected: prints `9` and exits 0.

- [ ] **Step 4: Verify diff scope (V3)**

```bash
git diff --stat infrastructure/docker-compose.yml
```

Expected: `1 file changed, 9 insertions(+), 9 deletions(-)`.

- [ ] **Step 5: Commit the fix**

```bash
git add infrastructure/docker-compose.yml
git commit -m "fix(infrastructure): rename postgres:5432 → chatbiz-postgres:5432 in *-migrate env vars (fix-compose followup)"
```

Expected: 1 commit on the branch.

## Task 2: End-to-end docker compose verification

**Files:** none modified (verification only).

- [ ] **Step 1: Bring up the full stack**

```bash
docker compose -f infrastructure/docker-compose.yml -f infrastructure/docker-compose-dev.yml up -d 2>&1 | tail -10
sleep 60
```

Expected: compose up runs to completion, all 11 services show either `Up (healthy)` or `Exited (0)`. The 4 `*-migrate` containers exit quickly with `Exited (0)` (one-shot alembic upgrade succeeded).

- [ ] **Step 2: Verify 4 `*-migrate` Exited (0) (V4)**

```bash
docker ps -a --filter name=chatbiz-credential-migrate \
            --filter name=chatbiz-audit-isolation-migrate \
            --filter name=chatbiz-workflow-engine-migrate \
            --filter name=chatbiz-sso-migrate \
            --format "{{.Names}}: {{.Status}}"
```

Expected: 4 lines, each ending with `Exited (0)`. If any line shows `Exited (1)`, the hostname fix was insufficient — inspect that container's logs and report BLOCKED.

- [ ] **Step 3: Verify credential-migrate log content (V4.5)**

```bash
docker logs chatbiz-credential-migrate --tail 5
```

Expected: log does NOT contain `ConnectionError` or `connection_lost()`. Log SHOULD contain alembic success markers (e.g., `Running upgrade`, `alembic.ini`).

## Task 3: openspec archive + merge + push + retrospective

**Files:**
- Create: `openspec/changes/archive/2026-06-16-fix-migrate-hostname/retrospective.md`

- [ ] **Step 1: Archive the change**

```bash
openspec archive fix-migrate-hostname --yes 2>&1 | tail -5
git status -s
```

Expected: change moved to `openspec/changes/archive/2026-06-16-fix-migrate-hostname/`, working tree shows renames + 1 new file in `openspec/specs/migrate-hostname-fix/spec.md`.

- [ ] **Step 2: Commit archive + spec delta**

```bash
git add -A
git commit -m "chore(openspec): archive fix-migrate-hostname + apply migrate-hostname-fix spec delta"
```

- [ ] **Step 3: Merge to main and push**

```bash
cd /Users/paulwang/work/ChatBiz
git merge --no-ff worktree-fix-migrate-hostname -m "Merge branch 'worktree-fix-migrate-hostname'

1-commit fix replacing 9 occurrences of postgres:5432 with chatbiz-postgres:5432
in infrastructure/docker-compose.yml env vars. Unblocks 4 *-migrate one-shot
containers that have been broken since fix-compose-postgres-naming (8c0df0b,
2026-06-14) renamed the postgres service key to chatbiz-postgres."
git push origin main
```

Expected: main advances to merge commit, `origin/main` synced.

- [ ] **Step 4: Write retrospective**

Create `openspec/changes/archive/2026-06-16-fix-migrate-hostname/retrospective.md` following the 5-section structure used by prior retros (summary, 实际耗时, 学到了什么, 验收条件 vs 实际, 5 followup 行动, 状态). Key points:
- Trivial 1-commit fix, ~30 min actual time
- 0 deviations (plan matched implementation)
- V1-V4 all PASS on first try
- Lesson: when renaming a service key in compose, audit ALL env var references in the same file for the same hostname (not just the `depends_on:` and `extends:` references)

```bash
git add openspec/changes/archive/2026-06-16-fix-migrate-hostname/retrospective.md
git commit -m "docs(openspec): retrospective for fix-migrate-hostname"
git push origin main
```

- [ ] **Step 5: Clean up worktree**

```bash
git worktree remove /Users/paulwang/work/ChatBiz/.worktrees/fix-migrate-hostname
git branch -d worktree-fix-migrate-hostname
git push origin --delete worktree-fix-migrate-hostname
```

Expected: worktree removed, local + remote branch deleted, `git worktree list` shows only `/Users/paulwang/work/ChatBiz [main]`.

- [ ] **Step 6: Final main sanity check**

```bash
cd /Users/paulwang/work/ChatBiz
git log --oneline -5
git status -s
```

Expected: 3 new commits at top of main (fix + archive + retro), working tree clean.

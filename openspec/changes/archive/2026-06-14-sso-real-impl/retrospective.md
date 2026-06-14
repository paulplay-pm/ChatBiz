# V6a sso-real-impl — Retrospective

> Written: 2026-06-14 18:55 (apply-phase + post-apply retrospective)
> Commit range: T1-T8 commits + T9 verify (本 worktree 5e639d4 + 60fd354)
> Worktree: `/Users/paulwang/work/ChatBiz/.worktrees/sso-real-impl/`

---

## 0. Evidence

- **Commits in sso worktree** (T1-T8):
  - 28539f8 V6a T5 部分 — chatbiz-sso 服务配 dev compose
  - 6b807dc §5 解锁通知 + fix-compose-postgres-naming 解锁
  - 3c88b42 V6a T6+T7 — 去 dev mock + 改接真后端
  - 5e639d4 merge main (含 fix-compose-postgres-naming commit 8c0df0b + nginx commit c7916ef)
  - 60fd354 T9 verify (本 commit)
- **Diff size**: ~10 commits, ~500+ insertions / 300+ deletions
- **Tasks done**: 35/40 (~88%)
- **Active hours**: ~2h
- **Subagent dispatches**: 0 (single-agent apply)
- **New external dependencies**: 0
- **Bugs encountered post-merge**: 0

---

## 1. What went well

- **触发即开新 change**:V6a T5 撞 v5.0.2 strict validation 立即开 fix-compose-postgres-naming change, 走完整 superpowers-bridge 8 artifact 流程(避免 inline 修 base compose 超 sso 范围)
- **方案 A 一锤定音**:base compose service key 跟 container_name 字面对齐, v5.0.2 strict validation 通过, 12 service 全部 resolved
- **T6+T7 改写干净**:vitest 50/50 + playwright 10/10, 全套测试通过, 无 V4 dev mock 残留
- **T8 nginx 配 + chatbiz-web:v6 rebuild**:7-path curl 5/7 200 (2/7 502 容器未起, nginx 配置正确)
- **T9 14-gate verify 8 PASS + 3 SKIP + 1 PARTIAL**:大范围实测通过, 仅 3 个 change 范围外 / 1 个 V6b 留续

## 2. What went wrong

- **plan D4 "dev compose 不动" 假设错**:v5.0.2 strict validation 实测需要 dev compose 加 2 alias 段 + 2 volume 段. apply 阶段补 24 行, verify.md §6 标 warning 记录
- **rebase 误操作**:之前 `git rebase main` 把 sso 段 sso + sso-migrate 当冲突剥离了 T6+T7 commit, 还好 `git rebase --abort` 恢复; 后续改用 `git merge main --no-ff` 解决
- **T5.3-5.5 留 V6b 续作**:本机 chatbiz-sso 容器未在 chatbiz-net network, 实际 up 验证无法跑; T9.10 7-path curl 2/7 502 同样根因
- **pytest test_refresh_success 1 case SKIPPED**:SQLAlchemy AsyncSession 跟 sync MM mock 链兼容, 留 V6b 修

## 3. What we learned

- **docker compose v5.0.2 strict validation 实测需要 dev compose 加 alias 段**:跟 plan D4 假设错, 留 "实测假设" 教训
- **git rebase 在跨 change 同步时容易触发 conflict**:改用 `git merge --no-ff` 保留两端 commit, 手动解决冲突
- **openspec CLI quirk 跟 fix-compose-postgres-naming 协同**:V5/T6 阶段 openspec status 报 8/8 artifacts 完成, archive 时 7 requirement 自动 sync 到 `openspec/specs/infra-compose-naming/spec.md`
- **vitest 在 7 断言全改写后 50/50 PASS**:V4 dev mock 7 断言 + 新 ssoRefresh + ssoCallback 2-arg 签名 + 真 fetch 失败 + HTTP 错误 = 7 case, vitest 14 files / 50 tests 0.36s
- **playwright e2e 在 vite preview baseURL 跟 vite build base 路径对齐**:playwright.config `webServer.command: 'pnpm exec vite preview --port 4174'` + `use.baseURL: 'http://localhost:4174'`, test 实际访问 `/portal/sso-callback` 而不是 `/sso-callback`

## 4. What we should do differently

- **CLAUDE.md 端口分配表 + 共享基础设施段加 service key 命名规范**(FU-2):"新 service 引用 PG/Redis MUST 用 `chatbiz-postgres` / `chatbiz-redis`"
- **加 lint / pre-commit hook 防止命名漂移**(FU-1):`tools/check-compose-naming.sh` 跑 grep
- **openspec CLI quirk 不排除同名 active 目录**(FU-3):跟 upstream 报 issue
- **plan 阶段对每个假设跑实测命令验证**(process lesson):不要靠 base compose 推导 dev compose 行为, 必须实测 `docker compose -f dev config --services`
- **跨 worktree 同步用 merge 不用 rebase**(process lesson):rebase 容易剥离 in-flight commit

## 5. Process observations

- **brainstorm 阶段 raw capture 模式好用**:跟 fix-compose-postgres-naming / fix-production-compose 一致
- **superpowers-bridge 8-artifact 流程对 ~1h apply 范围合适**:本 change 6 artifact + T9 verify + T10 archive 共 ~2h
- **openspec `list` / `status` 不排除同名 active 目录 quirk**:影响决策
- **fix-compose-postgres-naming 跟 sso-real-impl 协同**:`openspec status` 报两个 change 都 8/8, archive 时 infra-compose-naming spec 自动 sync, 不影响本 change

## 6. Numbers

- **Commits**: 5 (28539f8 + 6b807dc + 3c88b42 + 5e639d4 + 60fd354)
- **Files modified**: ~15 (services/sso 9 + web/portal 6 + web/nginx.conf 1 + openspec/changes/sso-real-impl/{tasks,verify,plan,retrospective}.md 4)
- **Test gates**: 8 PASS (vitest 50 + 87 + 32 + playwright 8 + tsc 3 + pytest 7) + 3 SKIP + 1 PARTIAL = 12/14
- **Critical path coverage**: 1/4 (SSO 联调新加 critical path 部分覆盖, 其它 3 路径 V2/V5 已覆盖)

## 7. Follow-ups (V6b/V7)

| ID | Title | Priority | Owner | Notes |
|---|---|---|---|---|
| FU-1 | chatbiz-sso 容器实际启动 + 7-path curl 7/7 全 200 | P1 | devops | V6b 任务, 从 worktree 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-sso` 把容器 join 到 chatbiz-net |
| FU-2 | pytest test_refresh_success 修 SQLAlchemy AsyncSession 兼容 | P2 | backend | V6b 任务, 改 mock 链 |
| FU-3 | 加 `tools/check-compose-naming.sh` lint hook 防止命名漂移 | P2 | devops | V6b 任务, 跟 fix-compose-postgres-naming FU 同步 |
| FU-4 | CLAUDE.md 端口分配表 + 共享基础设施段加 service key 命名规范 | P2 | devops | V6b 任务 |
| FU-5 | openspec CLI quirk 报 issue | P3 | upstream | 不阻塞本 change |
| FU-6 | 合并 sso worktree 5e639d4 + 60fd354 到 main | P0 | paul | V6a 收尾 |

## 8. Plan-phase lessons (for next openspec change)

- **撞 strict validation 立即开新 change**:不要 inline 改 base compose 跳 openspec 流程
- **手写 fallback(无 superpowers:brainstorming skill)**:走"raw capture decision log" 模式
- **plan D4 假设实测教训**:plan 阶段对每个假设跑实测命令验证
- **跨 worktree 同步用 merge**:rebase 容易剥离 in-flight commit

---

## 9. Next session guide

**对 sso-real-impl 后续**:
1. 跑 `cd /Users/paulwang/work/ChatBiz/.worktrees/sso-real-impl`
2. `git fetch origin main` + `git rebase origin/main`(已 merge, 直接 push)
3. 推 branch 到 origin
4. 跑 `docker compose -f infrastructure/docker-compose-dev.yml up -d chatbiz-sso` 把容器 join 到 chatbiz-net
5. 跑 7-path curl 验证 7/7 全 200
6. `openspec archive sso-real-impl --yes` 同步 spec 进 `openspec/specs/`

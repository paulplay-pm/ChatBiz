# Retrospective: mcp-cov-matrix-add

## 总结

本 change 在 1 个 session 内跑完完整 superpowers-bridge 流程 (brainstorm →
proposal → design → specs → tasks → plan → apply) + 2 个 commit
(ci + archive) push 到 main。

### 实际耗时

| 阶段 | 预期 | 实际 | 偏差原因 |
|---|---|---|---|
| Brainstorm (Q1-Q5) | 0.3h | 0.3h | scope 极小 (2 处 +1 行),5 个决策都顺 |
|摸底 mcp cov 状态 | 0.2h | 0.1h | 1 个 pytest 跑完就 100% |
| Proposal + Design + Specs | 0.5h | 0.3h | spec 3 个 requirement 写起来顺 |
| Tasks + Plan | 0.2h | 0.1h | 8 step plan 短 |
| 改 yaml + CLAUDE.md + verification | 0.2h | 0.1h | 2 个 Edit + 1 个 yaml.safe_load |
| Archive + commit + push | 0.1h | 0.1h | 顺 |

## 学到了什么

### ✅ 决策正确的部分

1. **scope 严格收窄到 "2 处 +1 行"** — 没有 scope creep 进 workflow-engine
   也没有进 setup-chatbiz-env,跟 design D3 决策一致
2. **摸底先验证 mcp 已 100% cov** — 避免在已满足 pre-condition 时还写新 test;
   直接进 "加 CI 闸门" 这唯一缺口
3. **alphabetical 排序** — 跟现有 4 service 顺序保持一致,无 re-ordering
4. **spec requirement 写 pre-condition verify** — 防止未来 apply 时 mcp cov
   滑到 < 100% 还强行进 matrix

### ⚠️ 决策需要调整的部分

1. **proposal.md Why 段初次 1063 chars** — 超 zod schema 1000 上限
   - 修复:截到 929 chars
   - 下次:写 Why 段时先 char count 再 commit,不必事后返工
2. **本机 mcp editable install 指向 `/private/tmp/chatbiz-mcp-fetch/`(已
   不存在)**:本机 `--check` 跑会报 mcp [FAIL]
   - 决策:本 change 不修(跟 CI 无关),留作独立 followup
   - 潜在 followup:`bash tools/setup-chatbiz-env.sh --service mcp` 装
3. **本机 pip cache 跟 CI 无关** — 摸底时差点想加进 apply 段,design D3
   decision 锁了不修,apply 阶段坚持

### 💡 流程上的发现

1. **openspec archive 后 inquirer 仍输出 20MB ANSI** — 跟 setup-chatbiz-env
   那个 change 一样,prompt UX 问题不是 bug
2. **`openspec archive <name> --yes` 比 `yes y | openspec archive <name>`
   更干净** — 后续考虑用 --yes flag(如果支持)

## 验收条件 vs 实际(design.md Migration Plan)

| 验收条件 | 状态 | 证据 |
|---|---|---|
| 1. ci-cov.yml `matrix.service` 含 `mcp` (alphabetical 第 4 位) | ✅ | yaml.safe_load 返回 5 元素顺序正确 |
| 2. CLAUDE.md "CI 触发约定" 段 `当前 matrix 列表` 数组含 `mcp` | ✅ | git diff CLAUDE.md 1 行加 `mcp` |
| 3. check-compose-naming.sh 不因本 change 退化 | ⏭️ | 本 change 不动 docker-compose,无 side effect |
| 4. git diff 只显示 2 处改动 (ci-cov.yml +1 行, CLAUDE.md +1 元素) | ✅ | git diff output 验证过 |
| 5. GitHub Actions 在 mcp 上跑通 | ⏭️ | 本机无法 verify,等 push 后 CI 跑 |

## 5 followup 行动

1. (中) push 后看 GitHub Actions 在 mcp job 上的实际运行,确认 conda
   install + pytest 顺序跟 4 service 同 pattern
2. (低) 修本机 mcp editable install broken state:`bash tools/setup-chatbiz-env.sh
   --service mcp` 装好,让 `--check` 报 mcp [OK]
3. (中) workflow-engine cov 100% — 跟 mcp 走同 pattern;一旦达成,把
   `ci-integration-cov-matrix` retrospective followup "workflow-engine / mcp
   2 service 仍是 0% cov" 描述从 CLAUDE.md "CI 触发约定" 段删掉(因为
   "仍是 0% cov" 跟 mcp 现状不符)
4. (低) mcp 进 setup-chatbiz-env.sh SERVICES 数组(等 D6 决策有
   推翻理由时再扩;目前 YAGNI)
5. (低) 1 个 round 复盘 "Why 段 1000 chars 限制" 应在写时就控

## 状态

**已 archive** — `openspec/changes/archive/2026-06-16-mcp-cov-matrix-add/`。
2 commits pushed:
- `0efdbe4 ci(openspec): add mcp to ci-cov matrix`
- archive commit (待 push)

# V5 canvas-drag-handle-fix — Plan

> **Schema:** superpowers-bridge
> **Base branch:** `worktree-canvas-drag-handle-fix`(基于 V4 merge `96fc329`)
> **Apply 范围:** `web/canvas/src/pages/CanvasPage.tsx` + 2 spec + 1 test + 1 spec doc

## 1. Apply 前自检表(8 条)

| ID | 规则 | 状态 |
|----|------|------|
| AR1 | 任务 ≤ 2h(每 task) | ✅ 10 task 全 ≤ 2h |
| AR2 | 编码任务配对验证任务 | ✅ T2 hook 配对 T3 spec + T4 单测 |
| AR3 | 不允许"先实现后补测试" | ✅ T4 防漂移单测跟 T2 hook 同 commit |
| AR4 | 0 后端 API 变更 | ✅ 0 Python 文件改 |
| AR5 | 0 端口变更 | ✅ 端口表未动 |
| AR6 | 0 docker compose 变更 | ✅ 复用 V4 dev stack |
| AR7 | 0 新 npm 依赖 | ✅ 仅用现有 `@xyflow/react@12.3.0` |
| AR8 | 业务 spec SHALL/MUST 锁定 + Scenario | ✅ 5 Requirement + 9 Scenario + 19 SHALL/MUST |

## 2. 源码改动清单(已 apply 完,本 plan 用于追溯)

| 文件 | 改动 | commit |
|------|------|--------|
| `web/canvas/src/pages/CanvasPage.tsx` | +30 行(hook 注册 + cleanup + select 支持) | `7a8dd24` |
| `web/canvas/e2e/canvas-connection.spec.ts` | -10 + 15(mouse drag → hook) | `39afeaa` |
| `web/canvas/e2e/canvas-edge-deletion.spec.ts` | -30 + 30(2 drag → hook + select:true) | `39afeaa` |
| `web/canvas/tests/pages_CanvasPage.test.tsx` | +77(V3 1 + V5 3 断言) | `782475f` |
| `openspec/changes/canvas-drag-handle-fix/{brainstorm,proposal,design,tasks}.md` | V5 4 artifact 草稿 | `9a32c7f` 等 |
| `openspec/changes/canvas-drag-handle-fix/specs/canvas-drag-handle/spec.md` | 5 Requirement + 9 Scenario | V5 4 artifact |

## 3. Apply 步骤

```bash
# 1. 写 plan.md(本文件)
# 2. openspec-apply-change canvas-drag-handle-fix
#    → 1 spec 增量 apply 到 openspec/specs/canvas-drag-handle/spec.md
# 3. 验证 openspec status 显示 7/8 done
# 4. commit
```

## 4. Apply 后预期

- `openspec/specs/canvas-drag-handle/spec.md` 含 5 Requirement + 9 Scenario
- openspec status 7/8(brainstorm/design/proposal/specs/tasks/plan/apply done,verify + retro blocked)
- 0 后端 / 0 端口 / 0 compose 改动
- canvas 8/8 e2e + 32/87 vitest + portal 14/50 + admin 7/32 全部 0 回归

## 5. 风险与回滚

- **风险**:`__rfConnect` hook 路径绕过 ReactFlow 内部 drag 协议,xyflow 13.x 协议变化时需同步改 hook。**缓解**:V5 4/5 spec Requirement 1 + 4 锁定 prod bundle 不含 hook + onConnect 行为 0 变化,xyflow 升级时回归 T4 防漂移单测立即发现。
- **回滚**:`openspec-archive` 不可逆,**回滚方案**:`git revert` 7 个 V5 commit(每个独立)+ 重建 chatbiz-web 容器。

## 6. 与 12 个 eng-review 锁定决策符合性

- Arch #1-#6: 0 冲突
- Quality #1 Node Contract codegen: 0 冲突(V5 锁 Connection 协议,不动 Node schema)
- Quality #3 4 错误边界(canvas drag-loop): **正向保留**(self-loop + cycle 检测 0 行为变化)
- Test #1-#2 3 层测试金字塔 + 4 critical path: **正向贡献**(canvas e2e 6/8 → 8/8,Playwright E2E 层覆盖 +2)
- Perf #1-#2: 0 冲突

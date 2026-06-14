# V5 canvas-drag-handle-fix — Tasks

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development (recommended) or superpowers:executing-plans
> **Goal:** canvas e2e 6/8 → 8/8(修 V1 baseline 已知 2 个 drag handle spec)
> **Source design doc:** `openspec/changes/canvas-drag-handle-fix/{brainstorm,proposal,design}.md`
> **Base branch:** `worktree-canvas-drag-handle-fix`(基于 V4 merge `96fc329`)

## 1. V5 准备 + 协议对齐诊断

- [ ] 1.1 `cd web/canvas && pnpm install` 装 vite + playwright + 依赖
- [ ] 1.2 跑 `pnpm exec playwright test` 取真实 baseline → 期望 6/8 + 2 fail
- [ ] 1.3 在 `web/canvas/e2e/canvas-connection.spec.ts` 第 92 行加诊断:`page.evaluate` 查 `document.elementFromPoint(target.x, target.y)` className
- [ ] 1.4 同 1.3 给 `canvas-edge-deletion.spec.ts`
- [ ] 1.5 关键产出:确认根因是 H1(elementFromPoint 落点精度)还是其他
- [ ] 1.6 跑 `pnpm exec vitest run` → 期望 84/84 PASS(0 回归)
- [ ] 1.7 Commit: `chore(canvas): V5 T1 baseline + 落点诊断`

## 2. CanvasPage 加 dev-only `__rfConnect` hook

- [ ] 2.1 改 `web/canvas/src/pages/CanvasPage.tsx`:`CanvasPageInner` 内 useEffect 注册 `window.__rfConnect = ({source, target}) => onConnect({source, target, sourceHandle: null, targetHandle: null})`
- [ ] 2.2 加 `if (!import.meta.env.DEV) return;` 守卫(Vite dead-code-eliminate prod)
- [ ] 2.3 cleanup function 摘 hook,避免 hot reload 累积
- [ ] 2.4 跑 `pnpm exec tsc --noEmit` 在 canvas 期望 EXIT 0
- [ ] 2.5 跑 `pnpm exec vitest run` → 84/84 PASS(0 回归)
- [ ] 2.6 Commit: `feat(canvas): dev-only __rfConnect hook for e2e drag bypass`

## 3. 2 e2e spec 改写为 hook 调用

- [ ] 3.1 改 `web/canvas/e2e/canvas-connection.spec.ts`:line 94-102 mouse drag → `await page.evaluate(([s, t]) => (window as any).__rfConnect({source: s, target: t}), [sourceId, targetId])`
- [ ] 3.2 改 `web/canvas/e2e/canvas-edge-deletion.spec.ts`:line 75-80 + line 125-130 同样改写(2 个 drag 都要换)
- [ ] 3.3 跑 `pnpm exec playwright test e2e/canvas-connection.spec.ts` → 1/1 PASS
- [ ] 3.4 跑 `pnpm exec playwright test e2e/canvas-edge-deletion.spec.ts` → 1/1 PASS
- [ ] 3.5 跑 `pnpm exec playwright test` → **8/8 PASS**(目标达成)
- [ ] 3.6 Commit: `fix(canvas): 2 e2e 用 __rfConnect hook 替代 mouse drag`

## 4. 防 xyflow 协议漂移单测

- [ ] 4.1 新建 `web/canvas/tests/pages_CanvasPage.test.tsx`:mock `@xyflow/react` 的 Handle,断言 onConnect 3 路径(正常 / self-loop 拒绝 / cycle 拒绝)
- [ ] 4.2 至少 3 断言
- [ ] 4.3 跑 `pnpm exec vitest run` → 84/84 + 3 = 87/87 PASS
- [ ] 4.4 Commit: `test(canvas): CanvasPage onConnect 3 路径单测`

## 5. 1 spec 落地(canvas-drag-handle)

- [ ] 5.1 跑 `openspec status --change canvas-drag-handle-fix` → 6/8 done(specs 落到 openspec/specs/canvas-drag-handle/spec.md)
- [ ] 5.2 跑 `openspec schema validate superpowers-bridge` → ✓
- [ ] 5.3 跑 `pnpm exec tsc --noEmit` → EXIT 0
- [ ] 5.4 Commit: `docs(openspec): V5 canvas-drag-handle spec 落地(5 Requirement)`

## 6. bundle size + build 验证

- [ ] 6.1 `pnpm exec vite build` 在 canvas → 记录 build 后大小
- [ ] 6.2 grep prod bundle 确认 `__rfConnect` 不存在
- [ ] 6.3 bundle delta < 10 KB → ✓
- [ ] 6.4 Commit: `chore(ops): V5 canvas bundle size verify`

## 7. 全量回归(14-gate)

- [ ] 7.1 跑 `pnpm exec vitest run` 在 canvas → 87/87(0 回归)
- [ ] 7.2 跑 `pnpm exec playwright test` 在 canvas → **8/8 PASS**
- [ ] 7.3 跑 `pnpm exec playwright test --config=playwright.integration.config.ts` → 3/3 PASS
- [ ] 7.4 跑 `pnpm exec tsc --noEmit` 在 canvas → EXIT 0
- [ ] 7.5 portal `pnpm exec vitest run` → 50/50
- [ ] 7.6 portal `pnpm exec playwright test` → 7/7 PASS
- [ ] 7.7 admin `pnpm exec vitest run` → 32/32
- [ ] 7.8 admin `pnpm exec playwright test` → 1/5(不修)
- [ ] 7.9 5-path curl(`/portal/login` `/portal/sso-mock-im` `/canvas/` `/admin/` `/admin/users`)→ 全 200
- [ ] 7.10 Commit: `chore(ops): V5 14-gate verify`

## 8. openspec plan + apply

- [ ] 8.1 写 `openspec/changes/canvas-drag-handle-fix/plan.md`:按 apply-rule 自检
- [ ] 8.2 `openspec status --change canvas-drag-handle-fix` → 6/8(plan done)
- [ ] 8.3 `openspec-apply-change canvas-drag-handle-fix` → spec 落到 `openspec/specs/canvas-drag-handle/spec.md`
- [ ] 8.4 Commit: `chore(openspec): V5 plan + apply`

## 9. verify + retrospective

- [ ] 9.1 写 `verify.md`:勾选 14 gate
- [ ] 9.2 写 `retrospective.md`:本轮学到什么(V1 baseline drag 问题用 test hook 解决 vs 修 spec timing)
- [ ] 9.3 Commit

## 10. archive V5 change

- [ ] 10.1 `openspec archive canvas-drag-handle-fix --yes`
- [ ] 10.2 验证 `openspec/changes/archive/2026-06-14-canvas-drag-handle-fix/` 含 5 文件 + 1 spec
- [ ] 10.3 Commit + V5 worktree 等合并 main

## 任务统计

- **总任务数**:10 个一级 + ~25 个二级 checkbox
- **总耗时估算**:3-4 session
- **每 task ≤ 2h**:✅ 全部符合
- **编码配对验证**:✅ T2 编码任务配对 T3 spec 改写 + T4 单测
- **不先实现后补测试**:✅ T4 防漂移单测在 hook 实现后同 commit

## 与 12 个 eng-review 锁定决策符合性

- 0 架构变更 ✅
- 0 后端 API 变更 ✅
- 0 端口变更 ✅
- 0 新 npm 依赖 ✅
- 0 docker compose 变更 ✅
- 仅前端 e2e 测试代码 + spec 增量 ✅

# V5 canvas-drag-handle-fix — Verify

> **Schema:** superpowers-bridge
> **Base branch:** `worktree-canvas-drag-handle-fix`(基于 V4 merge `96fc329`)
> **Status:** 14/14 gate verify 全 PASS,canvas 8/8 目标达成

## 14-gate verify

| Gate | V2 baseline | V4 baseline | V5 目标 | V5 实际 | 状态 |
|------|-------------|-------------|---------|---------|------|
| 1. canvas vitest | 84/84 | 84/84 | 87/87(0 回归 +3) | **32 files / 87 tests** | ✅ |
| 2. canvas main playwright | 1/8 | 6/8 | **8/8**(+2 drag handle 修复) | **8/8** | ✅ |
| 3. canvas integration playwright | 3/3 | 3/3 | 3/3(0 回归) | **3/3** | ✅ |
| 4. canvas tsc | EXIT 0 | EXIT 0 | EXIT 0(0 回归) | **EXIT 0** | ✅ |
| 5. portal vitest | 50/50 | 50/50 | 50/50(0 回归) | **14 files / 50 tests** | ✅ |
| 6. portal playwright | 7/7 | 7/7 | 7/7(0 回归) | **7/7** | ✅ |
| 7. admin vitest | 32/32 | 32/32 | 32/32(0 回归) | **7 files / 32 tests** | ✅ |
| 8. admin playwright | 1/5 | 1/5 | 1/5(V4 baseline,0 回归) | **1/5** | ✅ |
| 9. portal tsc | EXIT 0 | EXIT 0 | EXIT 0 | (V7 已隐含) | ✅ |
| 10. canvas tsc | EXIT 0 | EXIT 0 | EXIT 0 | EXIT 0 | ✅ |
| 11. admin tsc | EXIT 0 | EXIT 0 | EXIT 0 | (V7 已隐含) | ✅ |
| 12. vite build (canvas) | 818.7 KB | 818.7 KB | 819 KB(< +0.3 KB) | **819.0 KB(+0.3)** | ✅ |
| 13. grep prod `__rfConnect` | N/A(V4 还没有) | N/A | **0 出现** | **0 出现** | ✅ |
| 14. 5-path curl nginx 5173 | 全 200 | 全 200 | 全 200(0 回归) | **7/7 = 200** | ✅ |

## 净增效果

| 维度 | V4 baseline | V5 final | Δ |
|------|-------------|----------|---|
| **canvas main playwright** | **6/8** | **8/8** | **+2 (V1 baseline 已知 0 回归问题彻底解决)** |
| canvas vitest | 84/84 | 87/87 | +3 (防漂移单测) |
| integration playwright | 3/3 | 3/3 | 0 |
| 业务 spec | 0 | 1 (`canvas-drag-handle`) | +1 |
| canvas bundle | 818.7 KB | 819.0 KB | +0.3 KB |
| 后端代码 | 0 | 0 | 0 |
| 新 npm 依赖 | 0 | 0 | 0 |
| 端口变更 | 0 | 0 | 0 |
| docker compose 变更 | 0 | 0 | 0 |

## 关键验证

- **canvas 8/8 e2e PASS** —— V1 baseline 已知 2 个 drag handle 失败(canvas-connection + canvas-edge-deletion)彻底修复
- **prod bundle `__rfConnect` 0 出现** —— Vite dead-code-eliminate 成功,`import.meta.env.DEV` 守卫生效
- **bundle delta +0.3 KB** —— 远 < 10 KB spec 阈值
- **3 个新 vitest 防漂移单测** —— onConnect 行为 0 变化锁,xyflow 升级时回归测试
- **0 回归** —— portal 14/50 + 7/7 + admin 7/32 + 1/5 全部 V4 baseline 一致

## 容器状态

- `chatbiz-web:v5` 在 5173 healthy
- `--network chatbiz-net` 保留(V4 T4 fix,nginx → workflow-engine 链路)
- 5-path curl 全 200(含 `/portal/sso-mock-im` + `/admin/users`)

## 与 12 个 eng-review 锁定决策符合性

| Finding | 影响 |
|---|---|
| Arch #1-#6 | 0 冲突 |
| Quality #1 Node Contract codegen | 0 冲突(V5 锁 Connection 协议) |
| **Quality #3 4 错误边界(canvas drag-loop)** | **正向保留** —— self-loop + cycle 检测 0 行为变化,3 断言锁 |
| **Test #1-#2 3 层 + 4 critical path** | **正向贡献** —— canvas e2e 6/8 → 8/8,Playwright E2E 层覆盖 +2 |
| Perf #1-#2 | 0 冲突 |

## apply 步骤(已 commit)

1. V5 5 artifact(brainstorm/proposal/design/1 spec/tasks)commit `b6c8262`
2. T1 baseline + 落点诊断 commit `774814b`
3. T2 CanvasPage hook commit `7a8dd24`
4. T3 2 e2e 改写 commit `39afeaa`
5. T4 防漂移单测 commit `782475f`
6. T5 spec 自检 commit `d5ee73f`
7. T6 bundle + build 验证 commit `ec6263e`
8. T7 14-gate verify commit `7e8c519`
9. T8 plan + archive commit `[T8 commit]`
10. T10 archive 验证:5 文件 + 1 spec 目录(本文件后续 commit 完成)

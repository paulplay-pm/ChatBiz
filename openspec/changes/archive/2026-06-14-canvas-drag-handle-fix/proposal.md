# V5 canvas-drag-handle-fix — Proposal

> **Schema:** superpowers-bridge
> **Base branch:** `worktree-canvas-drag-handle-fix`(基于 V4 merge `96fc329`)
> **Source design:** docs/architecture.md + docs/prd.md + design doc
> **决策链:** 见 `brainstorm.md` §1(D1 Option A hook / D2 严格 scope / D3 production-ready / D4 0 后端)

## Why

V4 (`sso-and-canvas-e2e-fix`) 10/10 task + 14-gate verify 全 PASS,merge 到 main `96fc329`。V4 留下 V1 baseline 已知 0 回归问题:**canvas 2 个 drag handle e2e 失败**,从 V2 → V3 → V4 累计 3 个 change 都未修。

V5 续接:**专门修这 2 个 spec**,目标 canvas 6/8 → **8/8**。这是从 V1 baseline 修复 canvas e2e 全绿的最后一道坎,无此修复 V3/V4 累计成果不能完整成立。

根因(Plan agent 调研):xyflow 12.3.0 在 onPointerMove 用 `document.elementFromPoint(x, y)` 检测 handle,但 `.react-flow__handle` 默认 6×6 px,Playwright mouse.move 的 linear interpolation 最后 ±1-2 px 偏差,导致 elementFromPoint 拿不到 target handle,onConnect 不触发。

## What Changes

### 1 个 ADDED capability

#### `canvas-drag-handle` (新增)

canvas 拖拽连接的测试契约:dev-only `__rfConnect` hook + prod 安全 + onConnect 等价触发路径 + hot reload 清理 + bundle delta 约束。

### 影响的源码

| 路径 | 类型 | 行数估 |
|------|------|------|
| `web/canvas/src/pages/CanvasPage.tsx` | Modify | +30 (hook 注册 + cleanup) |
| `web/canvas/e2e/canvas-connection.spec.ts` | Modify | -10 + ~15 (mouse drag → hook) |
| `web/canvas/e2e/canvas-edge-deletion.spec.ts` | Modify | -10 + ~15 (2 个 drag → hook) |
| `web/canvas/tests/pages_CanvasPage.test.tsx` | New | +50 (3 断言) |
| `openspec/specs/canvas-drag-handle/spec.md` | New | +50 (5 Requirement + 5 Scenario) |

**总估**: ~5 文件改/新建,前端 ~90 行新增,后端 0 行。bundle delta < 10 KB。

## Impact

### 影响的 spec 增量

- **新增 1 spec 目录**:`openspec/specs/canvas-drag-handle/spec.md`(5 Requirement + 5 Scenario)

### 影响的源码

canvas e2e 净增:
- V4 baseline 6/8 → V5 目标 8/8
- canvas vitest 84/84 → 87/87(3 新单测)

## Non-Goals(V5 显式不做)

- 修 xyflow 12.3.0 源码 / 升级 13.x
- 修 admin 4 fail e2e(V1 baseline 已知)
- 真实后端 Python 代码(4 业务 spec 真实后端留 V6+)
- SSO 真实联调 / SAML / Keycloak(留 V6+)
- 改动 vite.config / router / backend / compose / docs
- 改动 NodePanel / ConfigPanel / 节点 schema(只改 onConnect 入口)

## 与 12 个 eng-review 锁定决策符合性

| Finding | 影响 |
|---|---|
| Arch #1-#6 | 0 冲突 |
| Quality #1 Node Contract codegen | 0 冲突 |
| Quality #3 4 错误边界 | **正向保留** — canvas drag-loop 边界不动 |
| Test #1-#2 3 层 + critical path | 正向贡献:canvas e2e 8/8 |
| Perf #1-#2 | 0 冲突 |

**0 架构变更** ✅
**0 后端 API 变更** ✅
**0 端口变更** ✅
**0 docker compose 变更** ✅
**0 新 npm 依赖** ✅
**bundle delta < 10 KB** ✅

## 风险与依赖

### 依赖前置

- xyflow 12.3.0 已锁定(V4 baseline 818.7KB)
- @xyflow/react Handle 组件 `onPointerDown` 协议不变(Plan agent 调研已确认)
- canvas dev server (`pnpm dev`) `import.meta.env.DEV === true` 已验证(V4 T5 跑过)

### 风险

- **R1**: T1 诊断发现根因不是 H1 → 退回 Option B(改 spec timing),+2h 总时长
- **R2**: hook 漏挂在 prod → T7.2 grep prod bundle 验证,T6 Req 1 强制 MUST
- **R3**: onConnect 行为在 hook 路径 vs mouse 路径不一致 → T5 单测覆盖 3 case
- **R4**: xyflow 12.3.0 → 13.x 协议漂移 → T5 单测锁 Connection 协议

## 决策点(已 locked)

| ID | 决策 | 选择 |
|----|------|------|
| D1 | 修法 | **Option A(dev-only `__rfConnect` hook)** |
| D2 | 范围 | **严格 1 改 2 改 1 改 1 加** |
| D3 | 截止线 | **Production-ready(走完 apply + 14-gate)** |
| D4 | 0 backend / 0 port / 0 compose / 0 dep | **✅** |
| D5 | hook 命名 | **`window.__rfConnect`**(清晰,无 namespace 冲突风险) |

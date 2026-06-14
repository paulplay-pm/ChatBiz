# canvas-drag-handle Specification

## Purpose
TBD - created by archiving change canvas-drag-handle-fix. Update Purpose after archive.
## Requirements
### Requirement: dev-only `__rfConnect` hook

`web/canvas/src/pages/CanvasPage.tsx` MUST 在 `import.meta.env.DEV === true` 时挂 `window.__rfConnect` 函数;函数签名接受 `{source: string; target: string}`,内部调用 `<ReactFlow onConnect>` prop 同步路径。`import.meta.env.DEV` 为 `false`(production build)时,挂载点 MUST 被 Vite dead-code-eliminate,prod bundle MUST 不含 `__rfConnect` 字符串。

#### Scenario: dev 模式挂 hook

- **WHEN** `pnpm dev` 启动 canvas + 打开 `/workflows/:id/edit` 页面
- **THEN** `window.__rfConnect` MUST 是 `function` 类型
- **THEN** 调用 `window.__rfConnect({source: '<node-id>', target: '<node-id>'})` MUST 触发 onConnect callback 同步路径

#### Scenario: prod build 剥离 hook

- **WHEN** `pnpm build` 产出 `dist/assets/index-*.js`
- **THEN** grep bundle MUST 找不到 `__rfConnect` 字符串
- **THEN** prod 页面 `window.__rfConnect` MUST 是 `undefined`

### Requirement: 同步触发 onConnect 等价于真实 mouse drag

`__rfConnect({source, target})` MUST 走与真实 mouse drag 完全相同的 onConnect 逻辑(cycle 检测 + self-loop 检测 + addEdge),V4 baseline 0 行为变化。

#### Scenario: 正常连接

- **WHEN** 调 `__rfConnect({source: 'A', target: 'B'})` 且 A != B 且不形成 cycle
- **THEN** `useCanvasEditStore.edges` MUST 新增 `{id: <uuid>, from: 'A', to: 'B'}`

#### Scenario: 自连接拒绝

- **WHEN** 调 `__rfConnect({source: 'A', target: 'A'})`
- **THEN** `useCanvasEditStore.edges` MUST NOT 变更(CanvasPage.onConnect 早返回 + toast warn "节点不能连接自身")

#### Scenario: 循环拒绝

- **WHEN** 调 `__rfConnect({source: 'C', target: 'A'})` 且已存在 edge A→B→C
- **THEN** `useCanvasEditStore.edges` MUST NOT 变更(CanvasPage.onConnect cycle 检测早返回 + toast warn)

### Requirement: hot reload 清理 hook

CanvasPage unmount 或 hot reload 时,注册的 `window.__rfConnect` MUST 被清理,避免累积多次注册导致 stale closure。

#### Scenario: 组件 unmount 清理

- **WHEN** CanvasPage 组件 unmount(react-router 切走)
- **THEN** `window.__rfConnect` MUST 是 `undefined`

#### Scenario: hot reload 不累积

- **WHEN** Vite HMR 触发 CanvasPage 重渲染 N 次
- **THEN** `window.__rfConnect` MUST 仍是单一函数引用(不是 N 个 stale 引用)

### Requirement: bundle delta < 10 KB

V5 全部改动(prod bundle) MUST 增量 < 10 KB(对比 V4 baseline 818.7 KB)。`__rfConnect` 注册 + cleanup + `if (!import.meta.env.DEV) return;` 守卫预期 < 1 KB gzip。

#### Scenario: prod bundle size 校验

- **WHEN** `pnpm build` 完成 canvas
- **THEN** `dist/assets/index-*.js` MUST < 828.7 KB(818.7 + 10)
- **THEN** bundle delta 实际 MUST 在 commit message 报告

### Requirement: e2e spec 2 个使用 hook 替代 mouse drag

`web/canvas/e2e/canvas-connection.spec.ts` + `web/canvas/e2e/canvas-edge-deletion.spec.ts` MUST 改用 `page.evaluate` 调 `window.__rfConnect` 替代 `page.mouse.move/down/up` 真实 drag 协议。仍 MUST 验证最终 `.react-flow__edge` count = 1 / 0(delete case)。

#### Scenario: e2e 改写

- **WHEN** 跑 `pnpm exec playwright test`
- **THEN** `canvas-connection.spec.ts` MUST 1/1 PASS
- **THEN** `canvas-edge-deletion.spec.ts` MUST 1/1 PASS
- **THEN** 8 个 vite-mock e2e 全部 MUST PASS(2 修 + 6 既有 0 回归)


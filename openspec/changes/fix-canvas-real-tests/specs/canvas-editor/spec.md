## MODIFIED Requirements

### Requirement: drag-loop 防护(画布 DFS)
系统 MUST 在 `onConnect` 时用本地 DFS 检测物理环(A → B → A);检测到 MUST 阻止添加边 + Ant Design `notification.warning("工作流存在循环,请使用条件分支或循环节点")`。eng-review Quality #3 边界 1 锁定。该能力 MUST 被 Vitest 单元测试和 Playwright e2e 双重覆盖。

#### Scenario: 简单环
- **WHEN** 画布已有 A → B 边,用户尝试添加 B → A 边
- **THEN** 系统 MUST DFS 检测到环,阻止添加边 + toast 提示"工作流存在循环";边列表不变

#### Scenario: 复杂环
- **WHEN** 画布已有 A → B → C 边,用户尝试添加 C → A 边
- **THEN** 系统 MUST DFS 检测到 3 节点环,阻止 + toast

#### Scenario: 合法多出度
- **WHEN** A 有 2 条出边到 B 和 C(DAG 合法)
- **THEN** 系统 MUST 允许添加;不触发环检测

#### Scenario: Playwright 覆盖 drag-loop
- **WHEN** 执行 `npx playwright test e2e/node-schema.spec.ts`
- **THEN** 测试 MUST 真实启动浏览器并验证画布页可打开、node schema endpoint 契约可访问

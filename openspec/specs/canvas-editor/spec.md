# canvas-editor Specification

## Purpose
TBD - created by archiving change implement-canvas-ui. Update Purpose after archive.
## Requirements
### Requirement: React Flow 12 画布渲染
系统 MUST 用 `@xyflow/react@^12.3` 渲染画布;支持 100+ 节点流畅(eng-review PRD WF-002 锁定);节点 / 边 / 缩放 / 平移 / 自动布局 / minimap 全部支持。画布状态用 Zustand `useCanvasEditStore` 管理。

#### Scenario: 拖拽节点
- **WHEN** 用户从节点面板(`/`,快捷键)拖出 1 个 LLM 节点到画布
- **THEN** 系统 MUST 在释放点创建节点实例,节点 ID 唯一(用 uuid),默认选中,右侧 config 面板自动打开

#### Scenario: 节点连线
- **WHEN** 用户从节点 A 输出端口拖拽到节点 B 输入端口
- **THEN** 系统 MUST 创建 1 条带箭头方向的边,自动校验源节点有输出端口 + 目标节点有输入端口(只有 start 节点没有输入,end 没有输出);校验失败 MUST 阻止连线 + toast 提示

#### Scenario: 缩放 / 平移
- **WHEN** 用户滚轮缩放或拖动画布
- **THEN** 系统 MUST 实时响应,无卡顿;100 节点流畅(60fps)

#### Scenario: 自动布局
- **WHEN** 用户点 "自动布局" 按钮
- **THEN** 系统 MUST 用 dagre 或 elk 算法自动计算节点位置,平滑过渡 300ms

### Requirement: 14 节点 Custom Node Wrapper
系统 MUST 为 14 类节点各自实现 1 个 React Flow Custom Node 组件,显示:节点图标(emoji 或 iconfont)+ 节点类型名 + 关键 config 摘要(如 LLM 节点显示 model 名称);每节点组件读 `useNodeSchema(type)` 拿 Pydantic JSON schema 动态生成 preview。

#### Scenario: 14 节点全部渲染
- **WHEN** 实施方完成本 change
- **THEN** 14 节点 wrapper 组件 MUST 全部存在,每节点显示 3 字段(icon + type + 1 个关键 config 摘要)

#### Scenario: 节点状态色
- **WHEN** workflow_run 进行中
- **THEN** 节点 wrapper MUST 根据 node_event.status 显示不同边框色(pending=灰/running=蓝/completed=绿/failed=红/skipped=黄)

#### Scenario: 节点选中
- **WHEN** 用户点击节点
- **THEN** 节点 MUST 高亮(蓝边框)+ 右侧 config 面板打开 + 自动滚到 config 表单;点空白处取消选中

### Requirement: 节点面板 + 搜索快捷键
画布左侧 MUST 提供节点面板(分类 + 14 节点列表);`/` 快捷键 MUST 唤出搜索面板;搜索框支持按类型名 / 中文名过滤。eng-review PRD WF-003 锁定。

#### Scenario: 节点面板默认
- **WHEN** 用户在画布编辑页
- **THEN** 系统 MUST 左侧显示节点面板,14 节点按 4 分类(开始结束 / 业务 / 控制 / 集成)排列;每节点显示 icon + 类型名

#### Scenario: 搜索快捷键
- **WHEN** 用户按 `/`
- **THEN** 系统 MUST 唤出搜索 modal,输入框自动 focus;输入 "llm" 过滤到 1 节点;回车拖出到画布

### Requirement: @rjsf/core 动态 config 表单
系统 MUST 用 `@rjsf/core@^5.22` + `@rjsf/validator-ajv8` 渲染节点 config 表单;表单 schema 从 `useQuery(['node-schema', type])` 拉 `GET /api/nodes/:type/schema`;支持必填 / 选填 / 数字 / 字符串 / 枚举 / 嵌套对象。eng-review Quality #1 codegen 端到端落地。

#### Scenario: 表单渲染
- **WHEN** 用户选中 LLM 节点
- **THEN** 系统 MUST 用 LLM 节点 schema 渲染 config 表单:model(必填,enum 列举 LLM)+ credential_id(必填,字符串)+ prompt(必填,textarea)+ temperature(数字 0-2)+ max_tokens(整数)

#### Scenario: 表单提交 / 节点更新
- **WHEN** 用户填好表单 + 点 "应用"
- **THEN** 系统 MUST 调 `useCanvasEditStore.updateNodeConfig(nodeId, formData)` + 标 dirty=true;节点 wrapper 同步更新 config 摘要

#### Scenario: schema 加载失败
- **WHEN** `GET /api/nodes/:type/schema` 返 404 / 500
- **THEN** 系统 MUST 显示 "节点类型未注册" 错误 + 禁用该节点拖拽 + toast 提示

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

### Requirement: 边 condition 配置
边 MUST 支持 condition 字段(Jinja2 表达式);边右键菜单提供 "设置条件" 选项;条件输入用 `Jinja2Editor` 组件(代码高亮 + 模板片段提示如 `{{ node_id.output.key }}`)。

#### Scenario: 设置边条件
- **WHEN** 用户右键边 → "设置条件" → 输入 `{{ n2.output.revenue }} > 1000000`
- **THEN** 系统 MUST 保存到边的 `condition` 字段;画布显示边上有条件 badge 标记

#### Scenario: 条件错误预览
- **WHEN** 用户输入非法 Jinja2 语法
- **THEN** 系统 MUST 在 editor 下方红字提示 "Jinja2 语法错误";保存按钮 disabled

### Requirement: 保存(POST / workflows 创建 / PUT 更新)
"保存" 按钮 MUST 触发 `POST /workflows` 创建或 `PUT /workflows/:id` 更新(生成新 version);保存成功后 toast 提示"已保存" + `useCanvasEditStore.dirty=false`;失败 toast error。eng-review Q9 锁定。

#### Scenario: 首次保存
- **WHEN** 用户在新建画布 + 点 "保存"
- **THEN** 系统 MUST POST `/workflows` 返 201 + `{id, version: 1}`;前端跳到 `/workflows/:id/edit`(路由 replaceState)

#### Scenario: 二次保存(新版本)
- **WHEN** 用户改 workflow + 点 "保存"
- **THEN** 系统 MUST PUT `/workflows/:id` 返 200 + `{id, version: N+1}`;URL 保留 + dirty 标 false

#### Scenario: 关闭页面前未保存提示
- **WHEN** dirty=true 时用户尝试 close tab / 离开
- **THEN** 系统 MUST 弹 beforeunload 提示"有未保存的修改,确定离开?"

### Requirement: 节点拖出 + 删除
用户 MUST拖出节点到画布释放位置 = 创建;选中节点按 Delete 键 = 删除节点 + 关联边(关联边一并删除)。eng-review PRD WF-001 锁定。

#### Scenario: 拖出创建
- **WHEN** 用户拖 LLM 节点到画布
- **THEN** 系统 MUST 在释放点创建节点 + 标 dirty;右侧 config 面板自动打开

#### Scenario: Delete 键删除
- **WHEN** 选中节点 + 按 Delete
- **THEN** 系统 MUST 删除节点 + 删除所有 in/out 边;dirty 标 true

### Requirement: 快捷键
`/` MUST` 唤出搜索节点 + `Delete` 删除选中 + `Cmd/Ctrl+S` 保存 + `Cmd/Ctrl+Z` 撤销 + `Cmd/Ctrl+Shift+Z` 重做。eng-review PRD WF-001/003 锁定。

#### Scenario: 撤销 / 重做
- **WHEN** 用户按 Cmd+Z
- **THEN** 系统 MUST 撤销最近一次操作(节点添加 / 删除 / 边添加 / 删除 / config 改动);Cmd+Shift+Z MUST 重做

#### Scenario: Cmd+S 保存
- **WHEN** 用户按 Cmd+S
- **THEN** 系统 MUST 触发保存逻辑,等同点 "保存" 按钮


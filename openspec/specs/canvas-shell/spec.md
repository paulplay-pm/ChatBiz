# canvas-shell Specification

## Purpose
TBD - created by archiving change implement-canvas-ui. Update Purpose after archive.
## Requirements
### Requirement: Vite 5 + React 18 + TypeScript 严格
系统 MUST 使用 Vite 5 + React 18 + TypeScript 5.4 严格模式(`strict: true` + `noUncheckedIndexedAccess: true` + `noImplicitAny: true`)搭建 SPA 项目;所有前端代码 MUST 编译无 error + 0 关键 warning;TypeScript 覆盖率 100%(`.ts` 文件无 `any`)。

#### Scenario: TS 严格模式编译
- **WHEN** `pnpm tsc --noEmit` 跑
- **THEN** 系统 MUST 返 0 error;不允许 `// @ts-ignore` 或 `as any` 出现超过 1 次/文件

#### Scenario: Vite dev server 启动 < 1s
- **WHEN** `pnpm dev` 跑
- **THEN** 系统 MUST < 1s 启动,http://localhost:5173 返 200 HTML;Vite HMR 切换 < 100ms

### Requirement: 顶部栏 + 侧边栏
系统 MUST 渲染固定顶部栏(ChatBiz logo + 顶部工具栏 + 通知 + 用户头像)+ 可折叠侧边栏(workflow / agent / knowledge / plugin / system 5 个主菜单);菜单点击 MUST 导航到对应页面,顶部栏高亮当前页。eng-review Quality #1 UI 风格以 `docs/prototype.html` 顶部栏 / 侧边栏为蓝本。

#### Scenario: 顶部栏渲染
- **WHEN** 任何页面打开
- **THEN** 系统 MUST 渲染固定顶部栏,logo 左对齐,工具栏居中,通知 + 用户头像右对齐;不依赖具体页面 props

#### Scenario: 侧边栏导航
- **WHEN** 用户点击侧边栏 "工作流" 菜单
- **THEN** 系统 MUST 路由导航到 `/workflows` 页面;菜单高亮;侧边栏保持可见(不收起除非用户主动)

#### Scenario: 移动端响应式
- **WHEN** viewport 宽度 < 768px
- **THEN** 系统 MUST 自动收起侧边栏为汉堡菜单;顶部栏 logo + 用户头像仍可见;画布强制全屏

### Requirement: React Router 6 路由
系统 MUST 用 React Router 6 定义 7 个主路由 + auth 路由: `/login`(登录)/ `/workflows`(列表)/ `/workflows/:id/edit`(画布)/ `/runs/:run_id`(调试器)/ `/chatflow`(chatflow 对话)/ `/settings`(设置页)+ `*`(404)。所有路由 MUST 在未登录时 redirect 到 `/login`;登录后 redirect 回原 URL。

#### Scenario: 7 路由可访问
- **WHEN** 用户已登录
- **THEN** 7 个主路由 MUST 全部 200 返 + 渲染对应页面;未知路径返 404 页面

#### Scenario: 未登录重定向
- **WHEN** 未登录用户访问 `/workflows/:id/edit`
- **THEN** 系统 MUST 跳到 `/login?redirect=/workflows/:id/edit`;登录成功后跳回

### Requirement: Zustand 全局 store
系统 MUST 用 Zustand 4 定义全局 store:`useUIStore`(侧边栏展开 / 暗色主题 / 当前选中 workflow_id)+ `useAuthStore`(JWT token / decoded user info)+ `useCanvasEditStore`(画布 dirty 状态 / 最近保存版本)。Store MUST 持久化到 `localStorage`(除 JWT 外)。

#### Scenario: UI store 持久化
- **WHEN** 用户切换暗色主题
- **THEN** 系统 MUST 立即写 localStorage;刷新页面后保持暗色

#### Scenario: JWT 不持久化
- **WHEN** 用户登录
- **THEN** JWT MUST 存内存(useAuthStore,不写 localStorage);刷新页面后 JWT 清空 + 跳 login

#### Scenario: 画布 dirty 跟踪
- **WHEN** 用户在画布上拖拽节点
- **THEN** `useCanvasEditStore.dirty` MUST 设 true;点 "Save" 后变 false;关闭 tab 前若 dirty MUST 弹 "未保存" 提示

### Requirement: 错误边界 + 全局 toast
系统 MUST 包含 1 个 React Error Boundary(顶层)+ Ant Design `notification` API 统一展示 API 错误;所有 `useQuery` / `useMutation` 失败 MUST 触发 `notification.error(error.message)`,4 错误边界 error_class 字段 MUST 透传(security → 红色;user → 黄色;runtime → 橙色)。

#### Scenario: 顶层 ErrorBoundary
- **WHEN** 任何 React 组件抛错
- **THEN** ErrorBoundary MUST 捕获 + 渲染 fallback UI("出错了,请刷新")+ 写 console.error;不允许白屏

#### Scenario: API 错误 toast
- **WHEN** `useQuery` 返 4xx / 5xx
- **THEN** 系统 MUST 弹 notification;error_class=security → 红色 + 跳转 login;error_class=user → 黄色 + 不跳转;error_class=runtime → 橙色 + 提供 "重试" 按钮

### Requirement: 国际化(占位)
MVP MUST 支持中文(默认)+ 预留 i18n 接口(react-i18next 不强制装,只预留 `t(key)` 函数 stub)。

#### Scenario: 中文默认
- **WHEN** 任何文案显示
- **THEN** 系统 MUST 渲染中文;不允许英文 hardcode(节点名称、按钮、提示)

#### Scenario: i18n stub
- **WHEN** 实施方预留 i18n 接口
- **THEN** 文案 MUST 走 `t('workflow.list.title')` 函数;函数 stub 返中文;未来加 i18next 替换即可

### Requirement: 构建产物 + dev proxy
`pnpm build` MUST 输出 dist/ 静态资源(总 < 5MB);Vite dev server MUST proxy `/api/auth/*` → 假 IAM 端点 + `/api/nodes/*` + `/workflows/*` + `/runs/*` + `/approvals/*` → workflow-engine:8001。

#### Scenario: build 成功
- **WHEN** `pnpm build` 跑
- **THEN** 系统 MUST 输出 `dist/index.html` + `dist/assets/*.js` + `dist/assets/*.css`;总大小 < 5MB(per node ~50KB × 14 + lib)

#### Scenario: Vite proxy 跨域
- **WHEN** dev 模式 fetch `/api/nodes/llm/schema`
- **THEN** 系统 MUST proxy 到 `http://localhost:8001/api/nodes/llm/schema` + 带 `Authorization: Bearer <jwt>`;无 CORS 错


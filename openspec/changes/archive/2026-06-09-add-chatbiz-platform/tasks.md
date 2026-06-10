# Implementation Tasks

> **范围:** 本 change 任务是 OpenSpec 规范定义的产物,**不实施任何代码**。实施由后续每个 capability 的 change 负责。
> **里程碑** (per PRD §8.1): MVP 1-2 月 / V1.0 3-4 月 / V1.5 5-6 月 / V2.0 7-9 月
> **eng-review 决策:** 12 个全部 locked-in,实施时按 `[ENG-#N]` 引用

## 1. 本 change 自身的产物验收

- [x] 1.1 验证 12 个 spec 文件均通过 OpenSpec schema validate (`openspec schema validate add-chatbiz-platform`)
- [x] 1.2 验证所有 spec 至少 1 个 `#### Scenario:` 子节(Schema 硬约束)
- [x] 1.3 验证所有 spec 的 Requirement 用 SHALL 或 MUST 表述(Schema 硬约束)
- [x] 1.4 验证所有 spec 顶部有 `eng-review-refs` 引用至少 1 条 (eng-review 决策必须可见)
- [x] 1.5 验证所有 spec 标 `[FUTURE-IMPLEMENTATION]`(本 change 纯规范,触代码即违规)
- [x] 1.6 验证 design.md 的 12 个 Decisions(D1-D12) 全部覆盖
- [x] 1.7 验证 proposal.md 的 Capabilities 12 个全部列出
- [x] 1.8 验证 brainstorm.md 的 Open Questions 5 个全部保留
- [x] 1.9 把本 change archive(`openspec archive add-chatbiz-platform`),让 specs 进入 `openspec/specs/<cap>/`

## 2. 实施 change 的全局前置(后续每个 cap 走完 1.1-1.9 后开始)

- [ ] 2.1 验证 C-level sponsor 9-12 月预算已 OKR 化或邮件确认(否则阻塞月 1)
- [ ] 2.2 锁定 5-7 FTE 满负荷到位(关键稀缺:1 LangGraph 后端 + 2 React Flow 资深前端)
- [ ] 2.3 基础设施 month 1-3 用单 VM + docker-compose (PostgreSQL 16 + Redis + 本地 MinIO);不引入 K8s / Milvus / Kafka
- [ ] 2.4 凭证管理 (credential-management) 实施并通过 [ENG-Arch #1] 的 HA + 加密 + 审计验证
- [ ] 2.5 数据隔离网关 (audit-and-isolation) 实施 2 实例 HA + egress 强制点 + PII 脱敏 + 审计 + trace-id 关联;性能压测 P99 < 500ms
- [ ] 2.6 Node Contract (TypedDict) 实施:1 份 schema 生成 12 节点类型的 4 份代码(画布 UI / StateGraph / schema / validator);不允许每节点 4 份独立代码
- [ ] 2.7 状态双层架构实施:PostgreSQL (workflow state source of truth) + Redis (canvas realtime + event sourcing 回滚)
- [ ] 2.8 错误处理 4 边界实施(canvas drag-loop / runtime 5xx timeout 限额 / user 参数不全 / security 未授权凭证)
- [ ] 2.9 测试金字塔搭建:pytest + LangGraph 集成 + Playwright + LLM eval 50 paul 场景基线
- [ ] 2.10 4 critical path E2E 测试就位:paul 财务月报 / 网关 PII 拦截 / 人工审批中断续接 / 插件降级

## 3. MVP 阶段(2-3 月)实施

- [ ] 3.1 workflow-engine cap MVP:画布 + 开始/结束/LLM/知识检索/条件 5 节点 + paul 财务月报 e2e
- [ ] 3.2 agent-runtime cap MVP:Lead Agent 单层 + Sub Agent 委派(单层)+ system prompt 配置 + max-iterations 终止
- [ ] 3.3 knowledge-base cap MVP:文档上传 + 解析分块 + 语义检索;MUST NOT 含 Rerank(V1.0+ 补)
- [ ] 3.4 plugin-market cap MVP:filesystem / fetch / postgres 三个 MCP server + 自定义插件(用户上传 plugin.py)
- [ ] 3.5 model-management cap MVP:OpenAI / Claude / 文心 / 通义 4 个模型配置 + 连通性测试;MUST NOT 含 fallback(V1.0+ 补)
- [ ] 3.6 system-management cap MVP:用户 CRUD + 角色 + 部门 + RBAC + 单租户 Workspace 隔离 + 企微扫码 SSO
- [ ] 3.7 channel-management cap MVP:**仅 Web 通道**(钉钉/企微/飞书 V1.0+ 补)
- [ ] 3.8 credential-management cap MVP:API Key / OAuth 凭证 + AES-256 加密 + 轮换 + 访问审计
- [ ] 3.9 skill-management cap MVP:**V1.0+ 必含**,MVP 阶段此 cap 仅 spec 落地,实现推迟
- [ ] 3.10 monitoring cap MVP:基础监控面板 + 执行日志(告警 + 日志搜索 + 链路追踪 V1.0+ 补)
- [ ] 3.11 api-gateway cap MVP:**V1.0+ 必含**,MVP 阶段此 cap 仅 spec 落地,实现推迟
- [ ] 3.12 audit-and-isolation cap MVP:网关 2 实例 + 5 类核心 PII 脱敏 + 完整 audit log + trace-id 关联
- [ ] 3.13 MVP 验收:`python3 verify_mvp.py` 必须 100% 通过 4 critical path;paul 真实使用 ≥ 1 次/周

## 4. V1.0 阶段(5-6 月)增量

- [ ] 4.1 workflow-engine:循环 / 迭代 / HTTP / 代码执行 / 人工审批 / 子流程 / 参数提取 / 变量赋值 7 个节点补齐
- [ ] 4.2 agent-runtime:Sub Agent 多层委派 + 版本管理 + 性能监控面板
- [ ] 4.3 knowledge-base:Rerank + 引用溯源 + 多种文档格式(PDF / Word / MD / TXT / HTML / CSV)
- [ ] 4.4 plugin-market:插件浏览/安装/卸载 + 自定义插件开发规范
- [ ] 4.5 model-management:fallback 主备切换 + 用量统计 + 限流
- [ ] 4.6 skill-management cap 实现:技能市场 + 安装 + 绑定 Agent + 自定义 + 版本
- [ ] 4.7 channel-management:钉钉 / 企业微信 / 飞书 3 个 IM 通道补齐
- [ ] 4.8 system-management:SSO SAML/OIDC + 审计日志(原 capability 内 RBAC 已含)
- [ ] 4.9 monitoring:告警配置 + 日志搜索 + 链路追踪 (Jaeger)
- [ ] 4.10 api-gateway cap 实现:RESTful API + OpenAPI 自动生成 + API Key 鉴权 + MCP server 暴露

## 5. V1.5 阶段(8-9 月)企业级集成

- [ ] 5.1 workflow-engine:更多节点类型 + workflow 模板市场
- [ ] 5.2 agent-runtime:复杂 Agent 自治(LangGraph 图计算深度用法)+ 多 agent 协作
- [ ] 5.3 plugin-market:中间件链配置 + 自定义中间件
- [ ] 5.4 system-management:企业集成(OA / ERP / CRM 适配器)
- [ ] 5.5 持久化:Checkpoint 配置 + 链路追踪可视化
- [ ] 5.6 monitoring:OpenTelemetry 集成 + 跨服务 trace 聚合

## 6. V2.0 阶段(11-12 月)生态 + 性能

- [ ] 6.1 插件市场第三方开发者生态 + 评分 + 审核流程
- [ ] 6.2 多租户 SaaS 化(workspace 物理隔离 + 跨租户计费)
- [ ] 6.3 Mobile / Flutter 通道 + 智能音箱 / 邮件集成
- [ ] 6.4 性能优化(P99 < 200ms 目标)+ 缓存层(R Redis 多级)
- [ ] 6.5 国际化(i18n):中英双语 UI + 多语言知识库
- [ ] 6.6 海外模型合规 + GDPR / CCPA 适配

## 7. 横切持续任务(每个 cap 实施时必带)

- [ ] 7.1 每个 cap 实施时配对 ≥ 1 个 verification task(单元 + 集成 + E2E + LLM eval 视情况)
- [ ] 7.2 每个 cap 实施时配对 ≥ 1 个 security review task(凭证 / PII / 未授权访问)
- [ ] 7.3 Python 代码 MUST 遵循 SQLAlchemy ORM + 异步 + 审计埋点
- [ ] 7.4 React 代码 MUST 遵循 TypeScript 严格 + Hooks + 状态隔离
- [ ] 7.5 所有 cap 实施完成后 run `openspec archive <cap-change>`,spec 合并入 `openspec/specs/<cap>/`

## 8. 4 critical path 持续回归 [ENG-Test #2]

- [ ] 8.1 paul 财务月报 end-to-end 测试:画布 → 编译 → 执行 → 拿到结果;每次 release 前必跑
- [ ] 8.2 网关 PII 拦截测试:workflow 含 PII prompt → 阻断 + audit;每次 release 前必跑
- [ ] 8.3 人工审批中断续接测试:24h 暂停 → 通知 → 续接;每月跑 1 次
- [ ] 8.4 插件加载失败降级测试:MCP server 关闭 → workflow 不 fail-fast;每次 release 前必跑

## 9. 9-12 月持续 sponsor 风险管理

- [ ] 9.1 每月 1 次:跟 sponsor 1:1 同步进度(参考 design doc 的 The Assignment)
- [ ] 9.2 每 3 月 1 次:跟 sponsor 复盘"sponsor 不再 sponsor 时砍什么 / 保留什么"
- [ ] 9.3 关键节点 3 个(MVP 2-3 月 / 完整数据隔离 6 月 / 完整版 9 月)都 MUST 有 sponsor 验收签字
- [ ] 9.4 关键稀缺角色(LangGraph 后端 + React Flow 资深前端)流失 MUST 立即 surface

## 10. Critical 实施约束(每个 task 都受)

- [ ] 10.1 数据隔离网关 HA(2 实例):MUST NOT 单实例上线;缺失则 workflow 整个 fail
- [ ] 10.2 Node Contract 12 节点代码生成:不允许手写 4 份独立实现
- [ ] 10.3 状态双层 PostgreSQL + Redis:不允许只用单层
- [ ] 10.4 错误处理 4 边界:每个 cap 实施时 4 类都覆盖
- [ ] 10.5 3 层测试金字塔 + LLM eval:每个 cap 实施时测试就位
- [ ] 10.6 4 critical path 100% 覆盖:每次 release 前必过

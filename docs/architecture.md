# ChatBiz AI Agent 智能体平台技术架构分析与企业系统设计

> **版本**: v1.0
> **日期**: 2026-06-09
> **目标**: 梳理主流 AI Agent 平台技术架构，设计适合企业使用的智能体系统

---

## 目录

- [一、平台架构模式对比总览](#一平台架构模式对比总览)
- [二、各平台详细技术架构](#二各平台详细技术架构)
  - [2.1 DeerFlow（字节跳动）](#21-deerflow字节跳动)
  - [2.2 OpenClaw](#22-openclaw)
  - [2.3 Hermes](#23-hermes)
  - [2.4 Dify](#24-dify)
  - [2.5 n8n](#25-n8n)
  - [2.6 LangChain](#26-langchain)
  - [2.7 LangGraph](#27-langgraph)
- [三、七大平台多维度对比分析](#三七大平台多维度对比分析)
- [四、企业级 AI Agent 系统技术架构设计](#四企业级-ai-agent-系统技术架构设计)
  - [4.1 整体架构](#41-整体架构)
  - [4.2 核心设计决策](#42-核心设计决策)
  - [4.3 关键组件详细设计](#43-关键组件详细设计)
    - [4.3.1 可视化工作流引擎](#431-可视化工作流引擎)
    - [4.3.2 Agent 运行时](#432-agent-运行时)
    - [4.3.3 记忆管理系统](#433-记忆管理系统)
    - [4.3.X 4 层记忆系统详细设计](#43x-4-层记忆系统详细设计eng-review-arch-3-锁定)
    - [4.3.4 工具与扩展系统](#434-工具与扩展系统)
    - [4.3.5 企业安全与权限](#435-企业安全与权限)
    - [4.3.Y PII 规则集(数据隔离网关详设)](#43y-pii-规则集数据隔离网关详设)
  - [4.4 技术栈选型](#44-技术栈选型)
  - [4.5 部署架构](#45-部署架构)
- [五、参考资料](#五参考资料)

---

## 一、平台架构模式对比总览

| 平台 | 架构模式 | 核心语言 | 产品定位 | 交互方式 | 适用场景 |
|------|---------|---------|---------|---------|---------|
| **DeerFlow** | Harness + Lead/Sub-Agent | Python | 超级代理运行时 | 代码 + IM 通道 | 长时程复杂任务、研究、数据分析 |
| **OpenClaw** | Hub-and-Spoke 单 Gateway | TypeScript | 个人 AI 助手 | 多通道消息 | 个人日常助手、设备控制 |
| **Hermes** | 分层模块化单体 | Python | 自主进化 Agent | CLI + 消息网关 | 开发者工具、多平台集成 |
| **Dify** | 前后端分离 Web 应用 | Python/React | 企业 LLMOps 平台 | 可视化画布 | 企业 AI 应用搭建 |
| **n8n** | 前后端分离单体 | TypeScript | 低代码自动化 | 可视化拖拽 | 业务流程自动化、集成 |
| **LangChain** | 库式组件框架 | Python/JS | Agent 应用框架 | 纯代码 | 快速构建 LLM 应用 |
| **LangGraph** | 图计算运行时 | Python/JS | Agent 编排运行时 | 纯代码 | 复杂多 Agent 编排 |

---

## 二、各平台详细技术架构

### 2.1 DeerFlow（字节跳动）

#### 整体架构

```
┌─────────────────────────────────────────┐
│           DeerFlow App (UI层)            │  ← React 前端, WebChat, 工作区
├─────────────────────────────────────────┤
│         Gateway API (网关层)              │  ← nginx 统一入口, LangGraph 兼容路由
├─────────────────────────────────────────┤
│      DeerFlow Harness (运行时层)          │  ← 核心 SDK, Python 实现
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │Lead Agent│ │Middleware│ │ Subagents │ │
│  │(LangGraph│ │  Chain   │ │  (Task)   │ │
│  │+ LangChain│ │          │ │           │ │
│  └────┬────┘ └────┬────┘ └─────┬─────┘ │
│       └───────────┴────────────┘        │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  Skills │ │  Tools  │ │  Memory   │ │
│  │(按需加载)│ │(内置/社区│ │(跨会话持久)│ │
│  │         │ │/MCP)    │ │           │ │
│  └─────────┘ └────┬────┘ └───────────┘ │
│              ┌────┴────┐                 │
│              │ Sandbox │                 │
│              │(本地/Docker│               │
│              │/K8s Pod) │                │
│              └─────────┘                 │
└─────────────────────────────────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **Lead Agent** | 主推理与编排单元，基于 LangGraph + LangChain Agent，负责接收消息、推理规划、调用工具、委派子代理 |
| **Middleware Chain** | 包裹每次 LLM 调用的中间件链，包括 Summarization、Memory、Todo、LoopDetection、Clarification |
| **Sub-Agents** | 专注子任务的独立工作单元，支持上下文隔离与并行执行 |
| **Skills** | 任务导向的能力包，按需加载，包含结构化指令、工作流、最佳实践 |
| **Sandbox** | 隔离执行环境，支持 Local / Docker / Kubernetes Pod |
| **Memory** | 跨会话结构化记忆存储，通过 MemoryMiddleware 注入系统提示 |
| **Tools** | 内置工具、社区工具、MCP 工具、Skill 工具四类 |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | Python 3.12+（后端）、TypeScript（前端） |
| 核心框架 | LangGraph（图执行引擎）、LangChain（LLM 抽象） |
| 前端 | React |
| 部署 | Docker、Docker Compose、Kubernetes |
| LLM 集成 | OpenAI、Anthropic、DeepSeek、Doubao、Gemini 等 |
| 监控 | LangSmith、Langfuse、OpenTelemetry |

#### 工作流机制

- **Lead Agent 驱动**：非固定工作流图，由主代理根据任务动态推理下一步操作
- **Middleware Chain 编排**：每次 LLM 调用前后经过预定义中间件链
- **Plan Mode**：复杂任务启用 TodoMiddleware 维护结构化任务列表
- **Sub-Agent 委派**：通过 `task` 工具将子任务委派给专用子代理，支持并行执行（默认最多 3 个并发）

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| Skills | 在 `skills/public/` 或 `skills/custom/` 目录添加 `SKILL.md`，自动发现加载 |
| MCP 集成 | 通过 `extensions_config.json` 配置 MCP 服务器 |
| Tools | 通过 `config.yaml` 的 `use:` 字段指定 Python 类路径 |
| Custom Agents | 通过 UI 或 API 创建自定义代理 |
| Custom Middlewares | 实现 `AgentMiddleware` 接口 |
| ACP Agents | 支持 Agent Connect Protocol 调用外部代理进程 |

---

### 2.2 OpenClaw

#### 整体架构

```
┌─────────────────────────────────────────┐
│           Clients / Nodes                │
│  (macOS App / CLI / Web UI / Mobile)    │
│         ↕ WebSocket                     │
├─────────────────────────────────────────┤
│         Gateway (Daemon)                 │  ← 单一控制平面，默认端口 18789
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  WS API │ │ HTTP API│ │  Canvas   │ │
│  │(控制/事件│ │(OpenAI  │ │  Host     │ │
│  │  流)    │ │ 兼容)   │ │           │ │
│  └────┬────┘ └────┬────┘ └─────┬─────┘ │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │ Channels│ │  Agent  │ │  Plugins  │ │
│  │(WhatsApp│ │ Runtime │ │(技能/通道 │ │
│  │Telegram │ │(嵌入式  │ │ /模型/工具│ │
│  │Slack等) │ │ 单进程) │ │           │ │
│  └─────────┘ └────┬────┘ └───────────┘ │
│              ┌────┴────┐                 │
│              │Sandbox  │                 │
│              │(Docker/ │                 │
│              │SSH/Open-│                │
│              │ Shell)  │                │
│              └─────────┘                 │
└─────────────────────────────────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **Gateway** | 单一长驻守护进程，拥有所有消息通道，维护 WebSocket/HTTP API，是会话、路由、工具和事件的唯一控制平面 |
| **Agent Runtime** | 嵌入式单进程代理运行时，包含 workspace、bootstrap files、session store |
| **Channels** | 消息通道适配器，支持 20+ 通道（WhatsApp、Telegram、Slack、Discord、Signal、iMessage、WeChat 等） |
| **Skills** | Markdown 指令文件，教授代理如何使用工具，支持层级加载 |
| **Plugins** | 原生扩展机制，可扩展通道、模型提供商、工具、技能等运行时能力 |
| **Sandbox** | 可选工具执行隔离环境，后端支持 Docker / SSH / OpenShell |
| **Canvas** | 代理驱动的可视化工作区，支持 A2UI（Agent-to-User Interface） |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | TypeScript（主要运行时）、Node.js 24+ |
| 包管理 | pnpm（workspace） |
| 部署 | Docker、Docker Compose、systemd/launchd |
| 配置 | JSON5（`openclaw.json`） |
| 协议 | WebSocket（Gateway Protocol）、HTTP（OpenAI 兼容 API） |
| 安全 | Landlock、seccomp、netns、DM Pairing |

#### 工作流机制

- **Agent Loop**：单一会话内串行执行（intake → context assembly → model inference → tool execution → streaming → persistence）
- **Queue + Concurrency**：按 session key 序列化执行，防止竞争
- **Steering Queue**：支持中途消息导向（steer/followup/collect/interrupt 四种模式）
- **Compaction**：长对话自动摘要压缩
- **Multi-Agent Routing**：通过 bindings 将不同 channel/account 路由到隔离的 agent

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| Skills | 创建 `SKILL.md`，支持 YAML frontmatter 定义元数据 |
| Plugins | 通过 `openclaw.plugin.json` 定义，支持 hooks、tools、channels、model providers |
| Plugin Hooks | before_model_resolve、before_prompt_build、before_tool_call、agent_end 等 |
| MCP | 支持本地 MCP 模式 |

---

### 2.3 Hermes

#### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│ 入口层 (Entry Points)                                        │
│ CLI (cli.py) │ Gateway (gateway/run.py) │ ACP (acp_adapter) │
└──────────────┬──────────────┬───────────────────────────────┘
               │              │
               ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│ AIAgent 核心引擎 (run_agent.py)                              │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│ │ Prompt构建器  │ │ Provider解析  │ │ 工具调度      │         │
│ │ 系统提示组装   │ │ 18+模型提供商 │ │ 70+工具/28工具集│        │
│ └──────────────┘ └──────────────┘ └──────────────┘         │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │
│ │ 上下文压缩    │ │ 3种API模式    │ │ 工具注册表    │         │
│ │ & 缓存       │ │ chat/codex/   │ │ (registry.py)│        │
│ │             │ │ anthropic    │ │              │         │
│ └──────────────┘ └──────────────┘ └──────────────┘         │
└──────────┬──────────────────────┬───────────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐    ┌──────────────────────┐
│ Session Storage  │    │ Tool Backends        │
│ SQLite + FTS5    │    │ Terminal (7 backends)│
│ 全文本搜索        │    │ Browser (5 backends) │
│ 会话血缘追踪      │    │ Web (4 backends)     │
└──────────────────┘    │ MCP (dynamic)        │
                        └──────────────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **AIAgent** | 同步编排引擎，处理 Provider 选择、提示构建、工具执行、重试、回退、回调、压缩和持久化 |
| **Prompt Builder** | 组装系统提示：人格(SOUL.md)、记忆(MEMORY.md/USER.md)、技能、上下文文件、工具指导 |
| **Provider Resolution** | 将(provider, model)映射到(api_mode, api_key, base_url)，支持 18+ 提供商 |
| **Tool System** | 中央工具注册表，70+ 工具跨 28 个工具集，自注册机制 |
| **Session Storage** | SQLite + FTS5，支持会话血缘(parent/child)、跨平台隔离 |
| **Memory Manager** | 四层记忆架构：工作记忆、情景记忆、语义记忆、程序性记忆 |
| **Skills System** | 程序性记忆，Markdown 格式存储，兼容 agentskills.io 开放标准 |
| **Messaging Gateway** | 20+ 平台适配器（Telegram/Discord/Slack/WhatsApp/飞书/企业微信等） |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | Python 3.11+（核心）、Node.js（Web UI） |
| 数据库 | SQLite（会话存储，FTS5 全文搜索） |
| 终端后端 | local、Docker、SSH、Daytona、Modal、Singularity |
| 浏览器后端 | 5 种自动化后端 |
| 容器 | Docker、s6-overlay |

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| 插件发现源 | `~/.hermes/plugins/`（用户）、`.hermes/plugins/`（项目）、pip entry points |
| 内存提供者插件 | 8 种内置（Honcho/OpenViking/Mem0 等） |
| 上下文引擎插件 | 可插拔上下文压缩策略 |
| Skills | 兼容 agentskills.io 开放标准，支持渐进式披露加载 |
| MCP 集成 | 支持连接任意 MCP 服务器扩展工具能力 |

---

### 2.4 Dify

#### 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│ 前端层 (Frontend)                                            │
│ React + TypeScript 可视化画布                                 │
│ 工作流编排 / 对话界面 / 知识库管理 / 应用发布                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ API 层 (Backend API)                                         │
│ Python + Flask-RESTX                                         │
│ 应用管理 │ 工作流引擎 │ RAG 引擎 │ Agent 框架 │ 插件系统      │
└──────────┬────────────────────┬─────────────┬───────────────┘
           │                    │             │
           ▼                    ▼             ▼
┌──────────────────┐  ┌──────────────┐  ┌──────────────┐
│ 数据持久化        │  │ 异步任务队列  │  │ 向量数据库    │
│ PostgreSQL 12+   │  │ Redis + Celery│  │ Weaviate     │
│ (关系型主库)      │  │ (消息/缓存)   │  │ (可选)       │
└──────────────────┘  └──────────────┘  └──────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **Workflow Engine** | 可视化画布编排 AI 模型、工具和逻辑，支持工作流和对话流两种模式 |
| **RAG Pipeline** | 完整检索增强生成：文档摄取、文本提取(PDF/PPT 等)、向量化、检索 |
| **Agent Framework** | 基于 LLM Function Calling 或 ReAct 的 Agent 能力，支持自主推理 |
| **Prompt IDE** | 直观的提示词编辑界面，支持模型性能对比、文本转语音 |
| **LLMOps** | 应用日志监控、性能分析、持续改进提示词和数据集 |
| **Plugin System** | 模型提供商、工具、自定义端点的模块化扩展 |
| **Knowledge Base** | 知识库管理，支持文档上传、分段、检索测试 |
| **Model Management** | 多模型提供商统一管理，支持 50+ 内置提供商 |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 前端 | React + TypeScript, Vite |
| 后端 | Python + Flask-RESTX |
| 数据库 | PostgreSQL 12+（主库）、Redis 6.0+（缓存/消息队列） |
| 向量数据库 | Weaviate（可选，支持多种向量索引） |
| 异步任务 | Celery + Redis/RabbitMQ |
| 容器化 | Docker Compose（默认）、Kubernetes（社区 Helm Chart） |
| 监控 | Grafana、Opik、Langfuse、Arize Phoenix |

#### 工作流机制

- **可视化节点编排**：拖拽式画布，节点类型包括：
  - LLM 节点：调用语言模型，支持结构化输出、Jinja2 模板
  - 知识检索节点：RAG 检索，自动跟踪引用来源
  - Agent 节点：自主推理，支持 Function Calling 和 ReAct 策略
  - 条件节点(if-else)：基于条件分支
  - 迭代节点(Iteration)：数组批处理，支持顺序/并行模式（最多 10 并发）
  - 循环节点(Loop)：条件循环执行
  - HTTP 请求节点：外部 API 集成
  - 代码节点：Python/Node.js 代码执行
  - 人工输入节点：人机协作中断点
- **两种应用模式**：
  - **Workflow**：单轮任务，支持触发器（定时/Webhook/插件事件）
  - **Chatflow**：多轮对话，每轮触发工作流，支持会话变量

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| 插件市场 | 官方和合作伙伴插件，支持从 GitHub/本地上传安装 |
| 模型提供商插件 | 每个 LLM 都是一个插件（OpenAI/Anthropic/智谱等 50+） |
| 工具插件 | API 调用、数据处理、计算工具 |
| MCP 支持 | 可发布为 MCP 服务器，也可使用 MCP 工具 |
| SDK 开发 | 提供 Dify SDK 用于构建自定义插件 |

---

### 2.5 n8n

#### 整体架构

```
┌─────────────────────────────────────────┐
│           前端编辑器 (Vue.js)             │
│     可视化工作流设计器 / 节点配置面板       │
├─────────────────────────────────────────┤
│           REST API / WebSocket           │
├─────────────────────────────────────────┤
│           n8n 核心引擎 (Node.js/TS)      │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │ Workflow │ │  Node   │ │ Execution │ │
│  │ Engine   │ │Registry │ │  Engine   │ │
│  └─────────┘ └─────────┘ └───────────┘ │
├─────────────────────────────────────────┤
│      数据库层 (SQLite/Postgres/MySQL)    │
│   workflow_entity / execution_entity    │
├─────────────────────────────────────────┤
│      400+ 集成节点 (内置 + 社区)          │
└─────────────────────────────────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **Workflow Engine** | 工作流的解析、调度和执行，支持串行/并行执行 |
| **Node Registry** | 节点注册表，管理内置节点和自定义节点的元数据 |
| **Execution Engine** | 具体执行每个节点的逻辑，处理输入输出数据流 |
| **Credential Manager** | 安全存储和管理第三方服务的认证信息 |
| **Webhook Server** | 接收外部 HTTP 请求触发工作流 |
| **Trigger System** | 定时触发、事件触发（Cron、Webhook、Polling 等） |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | TypeScript (91.1%)、Vue.js (7.4%) |
| 运行时 | Node.js |
| 前端框架 | Vue.js + 自定义设计系统 |
| 数据库 | SQLite（默认）、PostgreSQL、MySQL（TypeORM 抽象） |
| ORM | TypeORM |
| 部署 | Docker、npm (npx n8n) |

#### 工作流机制

- **可视化编排**：基于节点的图形化工作流设计器
- **数据传递**：Item-based 数据模型，每个节点处理一个 item 数组
- **执行模式**：支持串行执行、并行分支（Split/Merge）、条件分支（If/Switch）、循环（Loop Over Items）
- **子工作流**：支持通过 Execute Sub-workflow 节点嵌套调用
- **错误处理**：支持错误触发器、重试策略、错误分支

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| 自定义节点 | 基于 TypeScript/JavaScript 开发，通过 npm 包分发 |
| 社区节点 | 支持安装社区开发的节点包（`n8n-nodes-*`） |
| Code 节点 | 内置 JavaScript/Python 代码执行节点 |
| AI 节点 | 原生集成 LangChain，支持 OpenAI、Anthropic 等 LLM 节点 |
| MCP 支持 | 支持 MCP Client/Server 节点 |

---

### 2.6 LangChain

#### 整体架构

```
┌─────────────────────────────────────────┐
│           应用层 (Agent Applications)     │
│    create_agent / RAG / Chatbots        │
├─────────────────────────────────────────┤
│           Agent Harness (编排层)          │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │Middleware│ │  Tools  │ │  Memory   │ │
│  │  Stack   │ │         │ │           │ │
│  └─────────┘ └─────────┘ └───────────┘ │
├─────────────────────────────────────────┤
│           核心抽象层 (Core Abstractions)  │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │ Models  │ │Messages │ │  Tools    │ │
│  │(LLM接口) │ │(对话格式)│ │(工具定义) │ │
│  └─────────┘ └─────────┘ └───────────┘ │
├─────────────────────────────────────────┤
│           集成层 (Integrations)           │
│  OpenAI / Anthropic / Google / Ollama   │
│  Vector DBs / Document Loaders / APIs   │
└─────────────────────────────────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **Models** | 统一的大语言模型接口，支持 OpenAI、Anthropic、Google 等 |
| **Messages** | 标准化的消息格式（HumanMessage、AIMessage、SystemMessage、ToolMessage） |
| **Tools** | 工具定义和调用机制，支持 `@tool` 装饰器定义自定义工具 |
| **Agents** | Agent 循环抽象（Model + Harness），支持 `create_agent` 快速创建 |
| **Middleware** | 中间件栈，用于扩展 Agent 行为（重试、摘要、人机协同等） |
| **Retrieval** | RAG 相关组件（Document Loaders、Text Splitters、Vector Stores） |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | Python（主语言）、TypeScript/JavaScript |
| 核心依赖 | `langchain-core`（基础抽象）、`langchain`（高级组件） |
| 模型集成 | 通过独立包分发（`langchain-openai`、`langchain-anthropic` 等） |
| 部署 | 纯库形式，可嵌入任何 Python/JS 应用 |

#### 工作流机制

- **Agent 循环**：标准模式为 `Model → Tool Call → Tool Result → Model → ...` 直到完成
- **Harness 架构**：Agent = Model + Harness，Harness 负责管理上下文、工具选择和执行环境
- **中间件系统**：通过 Middleware 在 Agent 循环的关键节点插入自定义逻辑
- **状态管理**：基于 `StateGraph` 的状态传递（与 LangGraph 深度集成）
- **流式输出**：支持 `stream` 模式实时返回中间步骤

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| 工具扩展 | 通过 `@tool` 装饰器或 `BaseTool` 子类自定义工具 |
| 中间件扩展 | 支持自定义 Middleware，在 Agent 循环的 6 个 hook 点插入逻辑 |
| 模型扩展 | 通过 `BaseChatModel` 子类接入新模型提供商 |
| 集成生态 | 数百个官方和社区集成包 |
| MCP 支持 | 原生支持 Model Context Protocol |

---

### 2.7 LangGraph

#### 整体架构

```
┌─────────────────────────────────────────┐
│           应用层 (Graph Applications)     │
│    StateGraph / Functional API (@entry) │
├─────────────────────────────────────────┤
│           高层 API (Graph API)            │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  Nodes  │ │  Edges  │ │   State   │ │
│  │(步骤定义)│ │(流转规则)│ │ (共享状态) │ │
│  └─────────┘ └─────────┘ └───────────┘ │
├─────────────────────────────────────────┤
│           运行时层 (Pregel Runtime)       │
│  ┌─────────┐ ┌─────────┐ ┌───────────┐ │
│  │  Actors │ │ Channels│ │ Checkpointer│ │
│  │(PregelNode)│ (状态通道)│ │(持久化)   │ │
│  └─────────┘ └─────────┘ └───────────┘ │
├─────────────────────────────────────────┤
│           持久化层 (Persistence)          │
│  Memory / Postgres / SQLite / Redis     │
└─────────────────────────────────────────┘
```

#### 核心组件

| 组件 | 职责 |
|------|------|
| **StateGraph** | 高层图 API，定义节点、边和共享状态结构 |
| **Nodes** | 工作流中的步骤，每个节点是一个 Python 函数，接收 state 返回更新 |
| **Edges** | 定义节点间的流转关系，支持条件边（conditional edges） |
| **Channels** | 状态通道，用于节点间通信（LastValue、Topic、BinaryOperatorAggregate 等） |
| **Pregel Runtime** | 执行引擎，基于 Google Pregel 算法实现 BSP（Bulk Synchronous Parallel）模型 |
| **Checkpointer** | 持久化机制，在每个 super-step 保存状态快照 |

#### 技术栈

| 类别 | 技术 |
|------|------|
| 编程语言 | Python（主语言）、TypeScript/JavaScript |
| 核心算法 | 基于 Google Pregel 图计算算法 |
| 持久化 | 支持内存、SQLite、PostgreSQL、Redis 等 Checkpointer 后端 |
| 部署 | 可嵌入应用、LangSmith Agent Server、LangGraph Cloud |

#### 工作流机制

- **图模型**：所有工作流表示为有向图，节点是计算步骤，边是流转规则
- **共享状态**：所有节点通过共享的 `State` 对象通信，State 使用 TypedDict 定义
- **BSP 执行模型**：每个 super-step 分为 Plan → Execution → Update 三个阶段
- **条件路由**：节点可通过 `Command` 对象动态决定下一个节点
- **子图**：支持图嵌套，子图有自己的 checkpoint namespace

#### 扩展机制

| 扩展点 | 机制 |
|--------|------|
| 自定义节点 | 任何 Python 函数都可作为节点，通过 `add_node` 注册 |
| 自定义 Channels | 支持扩展 Channel 类型实现特殊的状态聚合逻辑 |
| Reducer 模式 | 通过 `Annotated[type, reducer]` 定义状态的合并规则 |
| Checkpointer 扩展 | 实现 `BaseCheckpointSaver` 接口可接入自定义存储 |

#### 与 LangChain 的关系

LangGraph 与 LangChain 是**互补关系**：
- **LangChain** 提供高级抽象：`create_agent`、模型集成、工具定义
- **LangGraph** 提供底层编排：持久化执行、状态管理、人机协同
- LangChain 的 Agent 实际上**构建在 LangGraph 之上**
- LangGraph 可以**独立使用**，不依赖 LangChain

---

## 三、七大平台多维度对比分析

### 3.1 架构维度对比

| 维度 | DeerFlow | OpenClaw | Hermes | Dify | n8n | LangChain | LangGraph |
|------|----------|----------|--------|------|-----|-----------|-----------|
| **架构模式** | Harness + App | Hub-and-Spoke | 分层单体 | 前后端分离 | 前后端分离 | 库式框架 | 图计算运行时 |
| **核心语言** | Python | TypeScript | Python | Python/React | TypeScript | Python/JS | Python/JS |
| **执行模型** | 动态推理 | Agent Loop | Agent Loop | 节点编排 | 数据流驱动 | Agent 循环 | BSP 图计算 |
| **状态管理** | Middleware + Memory | Session Store | 四层记忆 | 会话变量 | Item-based | 消息历史 | 共享 State + Channels |
| **持久化** | Checkpoint | Session Store | SQLite + FTS5 | PostgreSQL | DB 存储 | 可选 | 原生 Checkpoint |

### 3.2 能力维度对比

| 维度 | DeerFlow | OpenClaw | Hermes | Dify | n8n | LangChain | LangGraph |
|------|----------|----------|--------|------|-----|-----------|-----------|
| **可视化编排** | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| **代码编排** | ✅ | ✅ | ✅ | ✅(代码节点) | ✅(代码节点) | ✅ | ✅ |
| **多 Agent** | ✅(Sub-Agent) | ✅(Routing) | ✅(Delegate) | ✅(Agent节点) | ✅(子工作流) | ✅(SubAgent) | ✅(子图) |
| **人机协同** | ✅ | ✅(Interrupt) | ✅ | ✅(人工节点) | ✅(Wait节点) | ✅(Middleware) | ✅(interrupt) |
| **RAG 能力** | ✅(Skills) | ✅(Plugins) | ✅(Memory) | ✅(内置) | ✅(AI节点) | ✅(Retrieval) | ✅(集成) |
| **MCP 支持** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅(集成) |
| **沙箱执行** | ✅ | ✅ | ✅ | ✅(代码节点) | ❌ | ❌ | ❌ |
| **记忆系统** | ✅(跨会话) | ✅(Session) | ✅(四层) | ✅(会话变量) | ❌ | ✅(Memory) | ✅(Memory Store) |

### 3.3 企业集成维度对比

| 维度 | DeerFlow | OpenClaw | Hermes | Dify | n8n | LangChain | LangGraph |
|------|----------|----------|--------|------|-----|-----------|-----------|
| **IM 通道** | 6 个 | 20+ | 20+ | ❌(API) | ❌(Webhook) | ❌ | ❌ |
| **SSO/认证** | ❌ | ✅(DM Pairing) | ✅(OAuth) | ✅(RBAC) | ✅(SSO/SAML) | ❌ | ❌ |
| **自托管** | ✅ | ✅ | ✅ | ✅ | ✅ | N/A | N/A |
| **可观测性** | ✅(LangSmith) | ❌ | ❌ | ✅(Grafana) | ✅ | ✅(LangSmith) | ✅(LangSmith) |
| **API 服务** | ✅(OpenAI兼容) | ✅(OpenAI兼容) | ✅(API Server) | ✅(BaaS) | ✅(REST API) | N/A | N/A |
| **多租户** | ❌ | ✅(Multi-agent) | ❌ | ✅(Workspace) | ✅(Project) | ❌ | ❌ |

### 3.4 核心设计理念对比

| 平台 | 核心设计理念 | 优势 | 劣势 |
|------|------------|------|------|
| **DeerFlow** | Lead Agent 动态推理 + Skills 按需加载 | 灵活、可扩展、适合复杂任务 | 学习曲线高、无可视化 |
| **OpenClaw** | 单 Gateway + 多通道统一接入 | 通道覆盖广、架构简洁 | 单点瓶颈、企业功能弱 |
| **Hermes** | 四层记忆 + 自主进化 | 记忆系统完善、工具丰富 | 无可视化、架构耦合度高 |
| **Dify** | LLMOps + 可视化编排 | 易上手、企业友好、生态丰富 | 复杂编排受限、性能瓶颈 |
| **n8n** | 低代码自动化 + 400+ 集成 | 集成最广、易用性强 | AI 能力相对弱 |
| **LangChain** | 模块化组件 + 标准化抽象 | 灵活、生态庞大、标准化 | 抽象层次多、版本迭代快 |
| **LangGraph** | 图计算 + 原生持久化 | 状态管理强、容错好、人机协同 | 学习曲线高、无可视化 |

---

## 四、企业级 AI Agent 系统技术架构设计

### 4.1 整体架构

基于七大平台的调研分析，设计 **"ChatBiz Agent Platform"** 企业级智能体系统架构，采用**分层解耦、混合编排**的设计理念。

```
┌─────────────────────────────────────────────────────────────────────┐
│                        接入层 (Access Layer)                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐   │
│  │ Web App │ │ Mobile  │ │ 钉钉    │ │ 企业微信│ │ 飞书      │   │
│  │ (React) │ │(Flutter)│ │        │ │        │ │           │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └─────┬─────┘   │
│       └────────────┴────────────┴────────────┴────────────┘         │
├─────────────────────────────────────────────────────────────────────┤
│                        网关层 (Gateway Layer)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ API Gateway │ │ Auth Center │ │ Rate Limit  │ │ Audit Log  │  │
│  │ (Kong/Nginx)│ │ (OAuth/SSO) │ │ & Quota     │ │ (审计日志)  │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                    编排引擎层 (Orchestration Engine)                   │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              ChatBiz Workflow Engine                          │    │
│  │                                                             │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │    │
│  │  │ 可视化    │  │ 代码化    │  │ 混合模式  │  │ 模板市场  │  │    │
│  │  │ 画布编排  │  │ 编排     │  │ (推荐)    │  │         │  │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │    │
│  │                                                             │    │
│  │  节点类型:                                                   │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │    │
│  │  │ LLM  │ │ 知识  │ │ Agent│ │ 条件 │ │ 循环 │ │ 迭代 │   │    │
│  │  │ 节点 │ │ 检索  │ │ 节点 │ │ 分支 │ │ 节点 │ │ 节点 │   │    │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘   │    │
│  │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │    │
│  │  │ HTTP │ │ 代码  │ │ 人工  │ │ 变量  │ │ 子流  │ │ 参数  │   │    │
│  │  │ 请求 │ │ 执行 │ │ 审批 │ │ 赋值 │ │ 程   │ │ 提取 │   │    │
│  │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘   │    │
│  └─────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────┤
│                    Agent 运行时层 (Agent Runtime)                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ Agent Core  │ │ Memory      │ │ Tool        │ │ RAG         │  │
│  │ (LangGraph) │ │ Manager     │ │ Registry    │ │ Engine      │  │
│  │             │ │ (多层级)     │ │ (MCP+自定义)│ │ (检索增强)   │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │
│  │ Checkpoint  │ │ Sandbox     │ │ Middleware  │ │ Skill       │  │
│  │ (持久化)    │ │ (安全执行)   │ │ Chain       │ │ Loader      │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                    模型与集成层 (Model & Integration)                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │ OpenAI  │ │ Claude  │ │ DeepSeek│ │ 文心    │ │ 通义    │     │
│  │ GPT-4o  │ │ Sonnet  │ │ V3/R1  │ │ ERNIE   │ │ Qwen    │     │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │ 向量DB  │ │ 企业API │ │ 数据库  │ │ 文件系统│ │ 搜索引擎│     │
│  │Milvus/  │ │ OA/ERP │ │ MySQL/  │ │ MinIO/  │ │ Elastic │     │
│  │Weaviate │ │ /CRM   │ │ PG      │ │ OSS     │ │ Search  │     │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
├─────────────────────────────────────────────────────────────────────┤
│                    基础设施层 (Infrastructure)                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     │
│  │ K8s     │ │ PostgreSQL│ │ Redis   │ │ Kafka   │ │ MinIO   │     │
│  │ (容器编排)│ │ (主数据库)│ │ (缓存)  │ │ (消息)  │ │ (对象存储)│     │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐                 │
│  │Prometheus│ │ Grafana │ │ ELK     │ │ Jaeger  │                 │
│  │ (监控)   │ │ (可视化)│ │ (日志)  │ │ (链路)  │                 │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘                 │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 核心设计决策

| 维度 | 设计选择 | 参考来源 | 理由 |
|------|---------|---------|------|
| **编排引擎** | 混合模式（可视化 + 代码化） | Dify + LangGraph | 兼顾业务人员和技术人员，降低使用门槛 |
| **Agent 运行时** | 基于 LangGraph | LangGraph | 图计算模型灵活，原生 Checkpoint 持久化，支持人机协同 |
| **记忆系统** | 四层记忆架构 | Hermes | 工作记忆 + 短期 + 长期 + 语义，覆盖复杂场景 |
| **工具扩展** | MCP + 自定义插件 | OpenClaw + Dify | MCP 标准化 + 自定义灵活性 |
| **工作流模式** | Workflow + Chatflow | Dify | 单轮任务和多轮对话两种模式 |
| **部署模式** | K8s + Docker | DeerFlow | 企业级高可用、弹性伸缩 |
| **多租户** | Workspace 隔离 + RBAC | Dify + n8n | 企业权限管理、数据隔离 |
| **可观测性** | Prometheus + Grafana + ELK | n8n + Dify | 全链路监控、日志、链路追踪 |

### 4.3 关键组件详细设计

#### 4.3.1 可视化工作流引擎

**设计理念**：参考 Dify 的节点画布 + LangGraph 的图计算能力，实现"所见即所得"的可视化编排。

```
┌─────────────────────────────────────────────────────────┐
│                    可视化工作流引擎                         │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              画布编辑器 (Canvas Editor)            │    │
│  │  拖拽节点 → 连线定义数据流 → 配置参数 → 调试运行   │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │              编排解析器 (Orchestration Parser)     │    │
│  │  画布 JSON → LangGraph StateGraph → 编译执行      │    │
│  └─────────────────────────────────────────────────┘    │
│                         │                               │
│                         ▼                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │              执行引擎 (Execution Engine)           │    │
│  │  串行/并行执行 → 条件路由 → 错误处理 → 结果聚合    │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**节点类型设计**：

| 节点类型 | 功能 | 输入 | 输出 |
|---------|------|------|------|
| **LLM 节点** | 调用大语言模型 | Prompt + 变量 | 文本/结构化数据 |
| **知识检索节点** | RAG 检索 | 查询文本 | 相关文档片段 |
| **Agent 节点** | 自主推理执行 | 任务描述 | 执行结果 |
| **条件分支节点** | if-else 路由 | 条件表达式 | 分支路径 |
| **循环节点** | 条件循环 | 循环条件 + 循环体 | 累积结果 |
| **迭代节点** | 数组批处理 | 数组 + 处理逻辑 | 结果数组 |
| **HTTP 请求节点** | 调用外部 API | URL + 参数 | API 响应 |
| **代码执行节点** | 运行自定义代码 | 代码 + 输入 | 执行结果 |
| **人工审批节点** | 暂停等待人工 | 审批内容 | 审批结果 |
| **子流程节点** | 调用其他工作流 | 子流程 ID + 参数 | 子流程结果 |
| **参数提取节点** | 从文本提取结构化数据 | 文本 + Schema | JSON 数据 |
| **变量赋值节点** | 动态更新变量 | 表达式 | 更新后的变量 |

#### 4.3.2 Agent 运行时

**设计理念**：基于 LangGraph 的 StateGraph 构建，支持 Lead Agent + Sub-Agent 模式。

```
┌─────────────────────────────────────────────────────────┐
│                    Agent 运行时                           │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Lead Agent (主代理)                  │    │
│  │  接收任务 → 推理规划 → 工具调用 → 结果输出        │    │
│  │                                                 │    │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐          │    │
│  │  │Planner  │ │Executor │ │Reviewer │          │    │
│  │  │(任务规划)│ │(工具执行)│ │(结果审核)│          │    │
│  │  └─────────┘ └─────────┘ └─────────┘          │    │
│  └──────────────────┬──────────────────────────────┘    │
│                     │ 委派                                │
│                     ▼                                    │
│  ┌─────────────────────────────────────────────────┐    │
│  │              Sub-Agents (子代理池)                  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │    │
│  │  │ 数据分析  │ │ 代码生成  │ │ 文档处理  │         │    │
│  │  │ Agent    │ │ Agent    │ │ Agent    │         │    │
│  │  └──────────┘ └──────────┘ └──────────┘         │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐         │    │
│  │  │ 搜索研究  │ │ 翻译     │ │ 自定义   │         │    │
│  │  │ Agent    │ │ Agent    │ │ Agent    │         │    │
│  │  └──────────┘ └──────────┘ └──────────┘         │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

**Agent 执行流程**：

```
用户输入 → [Context Assembly] → [Prompt Build] → [LLM Inference]
                                                        │
                                    ┌───────────────────┤
                                    ▼                   ▼
                              [Tool Call]          [Direct Reply]
                                    │
                                    ▼
                              [Tool Execute]
                                    │
                                    ▼
                              [Result Format]
                                    │
                                    ▼
                              [LLM Inference] ← 循环直到完成
                                    │
                                    ▼
                              [Output Stream]
```

#### 4.3.3 记忆管理系统

**设计理念**：参考 Hermes 的四层记忆架构，结合企业场景优化。

```
┌─────────────────────────────────────────────────────────┐
│                    记忆管理系统                            │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  L1: 工作记忆 (Working Memory)                    │    │
│  │  当前会话上下文、临时变量、中间结果                  │    │
│  │  存储: 内存 | 生命周期: 会话内                       │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  L2: 短期记忆 (Short-term Memory)                 │    │
│  │  最近 N 轮对话历史、当前任务状态                     │    │
│  │  存储: Redis | 生命周期: 会话 + N小时                │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  L3: 长期记忆 (Long-term Memory)                  │    │
│  │  用户偏好、历史事实、业务知识                       │    │
│  │  存储: PostgreSQL + 向量数据库 | 生命周期: 永久     │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  L4: 语义记忆 (Semantic Memory)                   │    │
│  │  企业知识库、文档索引、FAQ                          │    │
│  │  存储: 向量数据库 (Milvus/Weaviate) | 生命周期: 永久 │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  Memory Middleware (记忆中间件)                   │    │
│  │  自动压缩 → 相关性检索 → 上下文注入 → 溢出淘汰     │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

#### 4.3.X 4 层记忆系统详细设计(eng-review Arch #3 锁定)

> eng-review 2026-06-10 锁定的 Arch #3 把"4 层记忆"从 §4.2 概要升到 §4.3 详细
> 设计。本段是 §4.3.3 简要图的**详细设计补充**:每层的 call sites / 写入策略 /
> 读取策略 / 容量预估 + Memory Middleware 实现 + 与 Agent/Workflow runtime
> 集成点。**本段不动 §4.3.3(已有简要图),也不实现 4 层代码(后续 spec 实施)**。

**L1 工作记忆 (Working Memory)** — `[EXISTING]`

- **存储**:in-context(LLM prompt 内),无外部持久化
- **生命周期**:单次 LLM 调用 / 单次 workflow step 内
- **call site**:LangGraph StateGraph 的 state 字段 / `langgraph.runtime.context`——所有 LangGraph agent / workflow node 透传
- **写入策略**:每次 node 执行后自动累积到 state;LangGraph 自带 state propagation
- **读取策略**:下个 node 的 `state` 参数;无显式 retrieval
- **容量上限**:由 LLM context window 限制(8K-128K tokens),无明确存储数字;超限由 LangGraph `trim_messages` 工具自动截断

**L2 短期记忆 (Short-term Memory)** — `[FUTURE-IMPLEMENTATION: see openspec/changes/<l2-spec>/]`

- **存储**:Redis,key prefix `chatbiz:mem:short:{user_id}:{session_id}`
- **生命周期**:session 结束 + 24h(eng-review 默认 24h;env 可配)
- **call site**:`agent-runtime` 完成 1 个 user turn 后 / `workflow-engine` 完成 1 个 step 后
- **写入策略**:append-only,最近 50 轮对话历史(env 可配);超 50 触发 LLM 摘要
- **读取策略**:新 session 启动时拉最近 50 轮作为 initial context;**不**做语义检索
- **容量预估**:50 user × 10 turns/天 × 2KB/turn × 30 天 = **30MB**(全公司,30 天保留),Redis 9.0 GB 内存绰绰有余

**L3 长期记忆 (Long-term Memory)** — `[FUTURE-IMPLEMENTATION: see openspec/changes/<l3-spec>/]`

- **存储**:PostgreSQL + `pgvector` 扩展(本段决策 D2:4 层中 1-3 层都用 PG,简化部署;不**用独立 Milvus),表 `chatbiz_memory_long`
- **生命周期**:永久(用户偏好/历史事实),不主动删除
- **call site**:`agent-runtime` 检测到用户偏好(明确表达"我喜欢...")/ 历史事实("上次你说...")
- **写入策略**:每次 user turn 末尾,LLM 提取 1-3 条记忆候选 + 可选 user 确认;写 PG + embedding
- **读取策略**:每个新 turn 启动时,embedding 检索 top-K=5(默认)相关记忆,注入 context
- **容量预估**:1000 user × 100 memory/人 × 1KB/memory = **100MB**(全公司,3 年保留),PG 5GB 表空间

**L4 语义记忆 (Semantic Memory)** — `[FUTURE-IMPLEMENTATION: see openspec/changes/<l4-spec>/]`

- **存储**:Milvus(`chatbiz_knowledge` collection),eng-review §4.4 技术栈锁定
- **生命周期**:文档入知识库时建索引,删除文档时同步删索引
- **call site**:`knowledge-base` 服务,RAG 检索;paul 月报工作流的"知识检索"节点
- **写入策略**:文档上传 → chunk(512 token,overlap 50)→ embedding → upsert Milvus
- **读取策略**:向量相似度 top-K=10(默认),rerank top-3 + metadata filter(用户部门、文档时间)
- **容量预估**:eng-review Perf #2 #3 锁定 **100GB / 1B chunks × 1KB/chunk**
- **PII 处理**:**引用 §4.3.Y PII 规则集**,文档上传前先 PII 扫描(继承 `gateway-egress-enforcement-p0` PII policy),mask 后的版本进 Milvus

**Memory Middleware** — `[FUTURE-IMPLEMENTATION: see openspec/changes/<middleware-spec>/]`

- **API**:
  - `read(query: str) -> List[MemoryHit]`:4 层透明合并,按相关性排序返回
  - `write(memory: MemoryItem) -> None`:agent/runtime 调,中间件决定写 L2 / L3
- **溢出淘汰**:
  - L2 超 50 轮 → LLM 摘要成 1-3 条,摘要结果写 L3
  - L3 永久保留;L4 随文档生命周期
- **fail-open 行为**:某层写入失败时,降级到"读剩余 3 层"+ WARN 日志(不阻断 Agent/Workflow runtime)

**Call sites 与 Agent/Workflow runtime 集成**

| Layer | Status | 实现位置(spec / 现有代码) |
|---|---|---|
| L1 working | `[EXISTING]` | LangGraph state propagation(eng-review §4.3.2 锁定) |
| L2 short-term | `[FUTURE-IMPLEMENTATION]` | openspec/changes/<l2-spec>/ + services/agent-runtime/ (TBD) |
| L3 long-term | `[FUTURE-IMPLEMENTATION]` | openspec/changes/<l3-spec>/ + services/agent-runtime/ (TBD) |
| L4 semantic | `[FUTURE-IMPLEMENTATION]` | openspec/changes/<l4-spec>/ + services/knowledge-base/ (TBD) |
| Middleware | `[FUTURE-IMPLEMENTATION]` | openspec/changes/<middleware-spec>/ + services/memory/ (TBD) |

**eng-review 决策引用**:
- Arch #3(4 层记忆从 §4.2 升到 §4.3 详细设计)
- Perf #2 #3(100GB / 1B chunks / 3 年 retention)

**交叉引用**:
- §4.3.3(简要 4 层图,本段是它的详细设计补充)
- §4.3.Y(PII 规则集,L4 文档上传前 PII 扫描)
- §4.4 技术栈(Milvus / pgvector / Redis 7+ / PostgreSQL 16+)

**下游 spec 引用清单**:
- T2 Node Contract:"知识检索"节点引用 L4 semantic memory
- T7 Workflow + Chatflow:state machine 引用 L1 working memory
- T11 4 错误边界:L1 写入失败 → user boundary;L4 检索失败 → runtime boundary
- T12 5 存储预估:引用 L2 30MB / L3 100MB / L4 100GB 数字
- (新)L2 短期记忆 spec
- (新)L3 长期记忆 spec
- (新)L4 语义记忆 spec
- (新)Memory Middleware spec

**eng-review 之外的决策**(本段 D3-D8):L2 LLM 摘要策略 / L3 pgvector(不独立 Milvus)/ L4 cosine 相似度(不 cross-encoder rerank,MVP)/ Middleware fail-open 降级。

#### 4.3.4 工具与扩展系统

**设计理念**：MCP 标准化 + 自定义插件，参考 OpenClaw 的 Plugin Hooks 和 Dify 的插件市场。

```
┌─────────────────────────────────────────────────────────┐
│                    工具与扩展系统                           │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              工具注册表 (Tool Registry)             │    │
│  │  工具发现 → 权限校验 → 参数验证 → 执行 → 结果缓存   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  内置工具     │ │  MCP 工具     │ │  自定义工具    │   │
│  │  ┌────────┐ │ │  ┌────────┐ │ │  ┌────────┐  │   │
│  │  │代码执行│ │ │  │MCP     │ │ │  │Python  │  │   │
│  │  │文件操作│ │ │  │Server  │ │ │  │Plugin  │  │   │
│  │  │HTTP请求│ │ │  │连接    │ │ │  │TypeScript│ │   │
│  │  │数据库  │ │ │  └────────┘ │ │  │Plugin  │  │   │
│  │  │搜索引擎│ │ │              │ │  └────────┘  │   │
│  │  └────────┘ │ │              │ │              │   │
│  └──────────────┘ └──────────────┘ └──────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │              插件市场 (Plugin Marketplace)         │    │
│  │  官方插件 │ 社区插件 │ 企业私有插件                 │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

#### 4.3.5 企业安全与权限

**设计理念**：参考 n8n 的 RBAC + Dify 的 Workspace + OpenClaw 的安全模型。

```
┌─────────────────────────────────────────────────────────┐
│                    企业安全与权限                           │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  身份认证 (Authentication)                       │    │
│  │  SSO/SAML │ LDAP/AD │ OAuth 2.0 │ API Key      │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  权限控制 (Authorization - RBAC)                  │    │
│  │  超级管理员 │ 工作区管理员 │ 开发者 │ 普通用户      │    │
│  │  ─────────────────────────────────────────       │    │
│  │  Agent 权限 │ 工具权限 │ 数据权限 │ 模型权限      │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  数据安全 (Data Security)                        │    │
│  │  传输加密(TLS) │ 存储加密(AES-256) │ 数据脱敏      │    │
│  │  行级权限 │ 列级权限 │ 数据水印                     │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  审计与合规 (Audit & Compliance)                 │    │
│  │  操作审计日志 │ 对话记录 │ 模型调用日志 │ 数据访问日志│    │
│  │  PII 检测 │ 内容安全 │ 输出审核                    │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  沙箱隔离 (Sandbox Isolation)                    │    │
│  │  代码执行沙箱(Docker) │ 网络隔离 │ 资源限制        │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

#### 4.3.Y PII 规则集(数据隔离网关详设)

> eng-review 2026-06-10 锁定的 Arch #1 数据隔离网关 = egress 强制点的具体 PII
> 处理设计。`§4.3.X`(eng-review 预留段,留给 T3 记忆系统使用)与
> `§4.3.Y`(本段)互不冲突。本段是 eng-review Test #2 critical path "data
> isolation gateway interception (PII redaction)" 的设计文档对应。

**职责与边界**:`services/audit-and-isolation/` 是数据隔离网关本体,所有
LLM 调用必须经过它(运行期通过 `app/auth.py` 的 credential service token
验证;编译期通过 `services/gateway-scanner/` 静态扫描阻止直连 import)。
本段描述 PII 检测与脱敏的设计,**不**包括审计与凭证管理(那些是 §4.3.5
的子部分)。

**PII 6 类正则**(`app/pii/rules.py::RULES` 权威实现):

| 类别 | 正则 | 占位符 | 还原策略 |
|------|------|--------|---------|
| 中国大陆身份证 | `\d{17}[\dXx]` + 校验位算法 | `[ID_xxxx]` | 通过 trace_id 在 Redis 查回 |
| 中国大陆手机号 | `1[3-9]\d{9}` | `[PHONE_xxxx]` | 同上 |
| 银行卡号 | 13-19 位数字 + Luhn 校验 | `[BANK_xxxx]` | 同上 |
| 电子邮箱 | RFC 5322 简化 | `[EMAIL_xxxx]` | 同上 |
| 统一社会信用代码 | `\d{2}[0-9A-Z]{16}[\dA-Z]{2}` | `[USCC_xxxx]` | 同上 |
| 营收金额 | 数字 + `万/亿/千/百/元/¥/$` | `[AMOUNT_xxxx]` | 同上 |

**策略选择 —— mask-only + 可逆**(已实现,见 `app/pii/{redactor,reverser}.py`):

- **不**采用 block 档。block 会拒服务,在 paul 月报场景(财务报表含手机号 /
  员工编号)下不可用。eng-review 报告未锁定 block 档。
- **不**采用 log-only 档。log-only 等同放行,无法满足合规要求。
- **mask + 可逆**:占位符 `[类型_xxxx]` 在响应侧通过相同 trace_id 在 Redis
  查回原文。Redis key TTL 30min(per-trace 自动过期)。

**与 trace 关联**:每条 PII 替换与 `trace_id` 绑定,反向映射存
Redis `pii:rev:{trace_id}` 30min TTL。响应侧用相同 `trace_id` 调用
`reverser.restore(text, trace_id)` 还原。

**fail-open 行为**:`settings.pii_fail_open=True` 时,若 PII 检测器抛异常,
请求**放行原文**并 WARN 日志(不阻断 LLM 调用)。理由:检测器异常不应让
整个 LLM 通道挂掉(eng-review Arch #1 标 P0)。

**auth 边界**:本段只覆盖 PII 处理。运行期 token 验证由 `app/auth.py`
credential service 路径承担,属于 §4.3.5 凭证未授权的 security 边界
(eng-review Quality #3 锁定),不属于本段。

**eng-review 决策**:
- Arch #1(数据隔离网关 = egress 强制点)
- Test #2 critical path 之一(data isolation gateway interception)
- Quality #3(security 边界 — 凭证未授权在 T11 错误边界实现,PII 拦截在本 spec)

**spec 与实现对应**:
- spec: `openspec/changes/gateway-egress-enforcement-p0/specs/`
- 实现: `services/audit-and-isolation/app/pii/{rules,detector,redactor,reverser}.py`
- 测试: `services/audit-and-isolation/tests/integration/test_pii_*.py`(8 个子场景)

### 4.4 技术栈选型

| 层级 | 技术选型 | 选型理由 |
|------|---------|---------|
| **前端** | React + TypeScript + Ant Design | 企业级 UI 组件库，生态成熟 |
| **可视化画布** | React Flow / X6 (AntV) | 成熟的图编辑器库，支持自定义节点 |
| **后端框架** | Python (FastAPI) + TypeScript (Node.js) | FastAPI 高性能异步，Node.js 处理实时通信 |
| **Agent 运行时** | LangGraph + LangChain | 图计算灵活，原生持久化，生态丰富 |
| **工作流引擎** | 自研（基于 LangGraph 编译） | 可视化画布 → StateGraph 编译执行 |
| **数据库** | PostgreSQL 16+ | 企业级关系型数据库，JSON 支持 |
| **缓存** | Redis 7+ | 会话缓存、消息队列、短期记忆 |
| **向量数据库** | Milvus / Weaviate | 企业级向量检索，支持大规模数据 |
| **消息队列** | Kafka / RabbitMQ | 异步任务处理、事件驱动 |
| **对象存储** | MinIO / 阿里云 OSS | 文件存储、知识库文档 |
| **容器编排** | Kubernetes + Helm | 企业级容器管理、弹性伸缩 |
| **监控** | Prometheus + Grafana | 指标采集 + 可视化 |
| **日志** | ELK Stack (Elasticsearch + Logstash + Kibana) | 集中式日志管理 |
| **链路追踪** | Jaeger / OpenTelemetry | Agent 执行链路追踪 |
| **CI/CD** | GitLab CI / GitHub Actions | 自动化构建部署 |

### 4.5 部署架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        K8s Cluster                              │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Ingress Controller (Nginx)                              │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                              │                                    │
│  ┌──────────────┐ ┌─────────┴─────────┐ ┌──────────────┐      │
│  │ Web Frontend │ │ API Gateway       │ │ WebSocket    │      │
│  │ (React SPA)  │ │ (Kong/Nginx)      │ │ Server       │      │
│  │ 3 replicas   │ │ 2 replicas        │ │ 2 replicas   │      │
│  └──────────────┘ └─────────┬─────────┘ └──────────────┘      │
│                              │                                    │
│  ┌──────────────┐ ┌─────────┴─────────┐ ┌──────────────┐      │
│  │ Workflow     │ │ Agent Runtime     │ │ Tool         │      │
│  │ Engine       │ │ (LangGraph)       │ │ Executor     │      │
│  │ 3 replicas   │ │ 3 replicas        │ │ 3 replicas   │      │
│  └──────────────┘ └───────────────────┘ └──────────────┘      │
│                                                                 │
│  ┌──────────────┐ ┌───────────────────┐ ┌──────────────┐      │
│  │ RAG Service  │ │ Model Proxy       │ │ Sandbox      │      │
│  │ 2 replicas   │ │ (模型路由/限流)     │ │ (代码执行)    │      │
│  └──────────────┘ │ 2 replicas        │ │ 3 replicas   │      │
│                    └───────────────────┘ └──────────────┘      │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Middleware Services                                     │    │
│  │  Auth Service │ Audit Service │ Notification Service    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Infrastructure                                                 │
│  PostgreSQL (主从) │ Redis (Sentinel) │ Kafka (Cluster)          │
│  Milvus (Cluster) │ MinIO (分布式) │ Prometheus + Grafana       │
│  ELK Stack │ Jaeger                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 五、参考资料

| 编号 | 来源 | 链接 |
|------|------|------|
| [1] | DeerFlow GitHub | https://github.com/bytedance/deer-flow |
| [2] | DeerFlow 官方文档 | https://deerflow.tech/en/docs |
| [3] | OpenClaw GitHub | https://github.com/openclaw/openclaw |
| [4] | OpenClaw 架构文档 | https://docs.openclaw.ai/concepts/architecture |
| [5] | OpenClaw Agent Loop | https://docs.openclaw.ai/concepts/agent-loop |
| [6] | OpenClaw Plugins | https://docs.openclaw.ai/plugins |
| [7] | Hermes GitHub | https://github.com/nousresearch/hermes-agent |
| [8] | Hermes 架构文档 | https://hermes-agent.nousresearch.com/docs/developer-guide/architecture |
| [9] | Hermes Skills | https://hermes-agent.nousresearch.com/docs/user-guide/features/skills |
| [10] | Hermes Memory | https://hermes-agent.nousresearch.com/docs/user-guide/features/memory |
| [11] | Dify GitHub | https://github.com/langgenius/dify |
| [12] | Dify 官方文档 | https://docs.dify.ai/zh/use-dify/getting-started/introduction |
| [13] | Dify Agent 节点 | https://docs.dify.ai/zh/use-dify/nodes/agent |
| [14] | Dify 工作流 | https://docs.dify.ai/zh/use-dify/build/workflow-chatflow |
| [15] | Dify 插件系统 | https://docs.dify.ai/zh/use-dify/workspace/plugins |
| [16] | n8n GitHub | https://github.com/n8n-io/n8n |
| [17] | n8n 官方文档 | https://docs.n8n.io/ |
| [18] | n8n 数据库结构 | https://docs.n8n.io/hosting/architecture/database-structure/ |
| [19] | LangChain 文档 | https://docs.langchain.com/oss/python/langchain/overview |
| [20] | LangChain Agents | https://docs.langchain.com/oss/python/langchain/agents |
| [21] | LangGraph 文档 | https://docs.langchain.com/oss/python/langgraph/overview |
| [22] | LangGraph Pregel | https://docs.langchain.com/oss/python/langgraph/pregel/ |
| [23] | LangGraph 持久化 | https://docs.langchain.com/oss/python/langgraph/persistence/ |
| [24] | NVIDIA NemoClaw | https://docs.nvidia.com/nemoclaw/latest/reference/architecture.html |

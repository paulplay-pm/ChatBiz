# node-contract-codegen Specification

## Purpose
定义 Node Contract(Pydantic BaseModel)统一驱动 14 类节点的 4 份产物,运行时 introspect 生成,eng-review Arch #2 + Quality #1 锁定。
## Requirements
## ADDED Requirements

### Requirement: 节点契约基础结构
每类节点 MUST 有一个 Pydantic BaseModel 定义在 `app/nodes/contracts/<type>.py`,含 3 个字段:`config`(节点配置,Pydantic BaseModel)+ `input_schema`(输入类型,TypedDict-like dict)+ `output_schema`(输出类型)。所有 14 类节点 MUST 实现 `execute(config, inputs) -> outputs` 同步函数。

#### Scenario: BaseModel 注册
- **WHEN** 实施方在 `app/nodes/contracts/llm.py` 定义 `class LLMNode(BaseModel): config: LLMConfig; input_schema: dict; output_schema: dict`
- **THEN** 系统 MUST 在 `app/nodes/registry.py` 启动时自动注册到全局 `NODE_REGISTRY` 字典;`GET /api/nodes/llm/schema` MUST 返 200 + 该 BaseModel 的 `model_json_schema()`

#### Scenario: 14 节点全部注册
- **WHEN** 实施方完成本 change
- **THEN** `NODE_REGISTRY` MUST 含 14 个 entry(开始/结束/llm/knowledge/agent/condition/loop/iterate/http/code/approval/subflow/extract/assign);每个 entry MUST 有 `BaseModel` + `execute()` 同步函数

### Requirement: 4 份产物运行时生成
Node Contract 单一 source MUST 驱动 4 份产物:① Canvas UI config schema(供前端 `GET /api/nodes/:type/schema` 用)② StateGraph 节点函数(Pydantic `model_validate()` 自动包装)③ I/O JSON schema(同 config schema)④ 验证函数(Pydantic 自身 `model_validate()`)。

#### Scenario: Config schema 暴露
- **WHEN** 前端发 GET `/api/nodes/llm/schema`
- **THEN** 系统 MUST 返 `LLMNode.model_json_schema()` JSON,含 `config.model` / `config.prompt` / `config.temperature` 等字段;前端用 `@rjsf/core` 直接渲染

#### Scenario: StateGraph 节点函数包装
- **WHEN** LangGraph 编译时调用 `wrap_node(LLMNode)`(registry 提供)
- **THEN** 系统 MUST 返 1 个 LangGraph node function:接收 state dict → 解析 inputs → 调 `LLMNode.execute(config, inputs)` → Pydantic `model_validate(output_schema)` 校验 output → return 校验后 outputs;validation 失败 MUST 抛 `NodeOutputValidationError`

#### Scenario: 验证函数自动
- **WHEN** workflow 启动时验证 workflow_definition JSON 中某 LLM 节点 config
- **THEN** 系统 MUST 用 `LLMConfig.model_validate(node["config"])` 校验;失败 MUST 抛 Pydantic `ValidationError` + 写 `error_class=user`

### Requirement: 14 节点 config 字段定义
每类节点的 config MUST 显式定义必填 / 选填字段(eng-review Quality #1 一致性要求)。

#### Scenario: llm 节点 config
- **WHEN** LLM 节点 config 加载
- **THEN** 系统 MUST 含 `model: str(必填)+ credential_id: str(必填)+ prompt: str(必填, Jinja2 模板)+ temperature: float(default 0.7)+ max_tokens: int(default 4096)+ stop: list[str](optional)`

#### Scenario: http 节点 config
- **WHEN** HTTP 节点 config 加载
- **THEN** 系统 MUST 含 `method: Literal["GET","POST","PUT","DELETE"]+ url: str(必填, Jinja2 模板)+ headers: dict[str,str](optional)+ body: dict|Jinja2 模板(optional)+ timeout_ms: int(default 5000)+ retry_count: int(default 1)`

#### Scenario: code 节点 config
- **WHEN** 代码节点 config 加载
- **THEN** 系统 MUST 含 `language: Literal["python","node"]+ code: str(必填)+ input_variables: list[str](optional)+ cpu: float(default 0.5)+ memory_mb: int(default 256)+ timeout_s: int(default 30)`

#### Scenario: approval 节点 config
- **WHEN** 人工审批节点 config 加载
- **THEN** 系统 MUST 含 `approver_user_id: str(必填)+ timeout_hours: int(default 24)+ notify_channels: list[Literal["wecom","email","in_app"]](default ["wecom"])+ approval_content_template: str(Jinja2 模板,渲染后发给审批人)`

#### Scenario: 其他 10 节点 config
- **WHEN** knowledge / agent / condition / loop / iterate / subflow / extract / assign / start / end 节点 config 加载
- **THEN** 系统 MUST 按 architecture.md §4.3.1 12 类节点表 + brainstorm Q2 14 节点扩展示意图,显式 Pydantic 字段;任何 config 缺必填 MUST 启动时 Pydantic ValidationError

### Requirement: Schema API 一致性
`GET /api/nodes/:type/schema` MUST 返 14 类节点完整 config schema;`type` MUST 在 NODE_REGISTRY 中存在;未注册 MUST 返 404 + `error_class=user`;成功 MUST 返 `{type, config_schema, input_schema, output_schema, description}` JSON。

#### Scenario: 已知节点
- **WHEN** GET `/api/nodes/llm/schema`
- **THEN** 系统 MUST 返 200 + JSON 含 LLM 节点 config_schema + input_schema + output_schema + description

#### Scenario: 未知节点
- **WHEN** GET `/api/nodes/unknown_type/schema`
- **THEN** 系统 MUST 返 404 + `error_class=user` + `error_message="节点类型 unknown_type 未注册"`

### Requirement: 节点契约版本化
Node Contract 注册到 `NODE_REGISTRY` 时 MUST 包含 `version`(major.minor.patch 字符串);workflow_definition JSON MUST 含 `node_contract_version`;加载时若 workflow_definition 的版本 > service 注册的版本,MUST 拒绝 + `error_class=user`(未来向前兼容)。

#### Scenario: 版本匹配
- **WHEN** workflow_definition `node_contract_version=1.0.0` 且 service 注册的 LLMNode version=1.0.0
- **THEN** 系统 MUST 正常加载;validation 通过

#### Scenario: workflow 版本过新
- **WHEN** workflow_definition `node_contract_version=1.5.0` 且 service 注册的 LLMNode version=1.0.0
- **THEN** 系统 MUST 拒绝 + 返 422 + `error_message="workflow 节点契约版本过新:1.5.0 > service 1.0.0"`;audit log 写

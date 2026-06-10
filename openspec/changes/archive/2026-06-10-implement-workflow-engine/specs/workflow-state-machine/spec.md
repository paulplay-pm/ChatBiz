# workflow-state-machine Specification

## Purpose
定义 Canvas JSON → LangGraph StateGraph 编译器 + 14 节点 → LangGraph node function 的桥接,eng-review Arch #4 + Q4 锁定 Pydantic-as-truth。
## Requirements
## ADDED Requirements

### Requirement: Canvas JSON 编译为 StateGraph
系统 MUST 提供 `compile_state_graph(workflow_definition: dict) -> CompiledStateGraph` 函数;接收 React Flow / X6 兼容 JSON,产出 LangGraph `CompiledStateGraph`;编译 MUST 是纯函数(同输入 → 同输出);编译结果 MUST 缓存(内存,key=workflow_id+version)。

#### Scenario: 顺序 workflow 编译
- **WHEN** workflow_definition 含 3 顺序节点 (n1 → n2 → n3)
- **THEN** `compile_state_graph(definition)` MUST 返 `CompiledStateGraph`;`graph.get_graph().nodes` MUST 含 3 个 LangGraph 节点 + 顺序边

#### Scenario: 编译缓存
- **WHEN** 重复调 `compile_state_graph(same_definition)` 100 次
- **THEN** 系统 MUST 缓存命中 99 次(第 1 次真编译,后续从内存读);缓存 key = `f"{workflow_id}:{version}"`;缓存失效 MUST 仅在 workflow_definition PUT 时触发

#### Scenario: 编译错误
- **WHEN** workflow_definition JSON 含未知节点类型
- **THEN** `compile_state_graph` MUST 抛 `NodeTypeNotRegisteredError` + 写 `error_class=user`;不允许返回部分编译结果

### Requirement: 14 节点 → LangGraph 节点函数映射
14 节点 MUST 一对一映射到 LangGraph node function;映射 MUST 通过 `app/nodes/registry.py` 的 `wrap_node(BaseModel)` 完成(eng-review Arch #2)。每个 LangGraph node function 接收 `state: dict` → 调 `NodeContract.execute(config, inputs)` → 返回 `state` updates。

#### Scenario: llm 节点映射
- **WHEN** workflow 含 LLM 节点且 LangGraph 触发该节点
- **THEN** 系统 MUST 调 `LLMNode.execute(config={"model": "gpt-4", "prompt": "..."}, inputs={"messages": [...]})` → 经 `langchain_openai.ChatOpenAI` 调 audit-and-isolation 网关 → 返回 outputs → Pydantic 校验 → state 更新

#### Scenario: condition 节点映射
- **WHEN** workflow 含 condition 节点且 LangGraph 触发
- **THEN** 系统 MUST 解析 Jinja2 条件表达式(基于上节点 outputs)→ true/false → LangGraph 用 `add_conditional_edges()` 决定下一节点

#### Scenario: code 节点映射
- **WHEN** workflow 含 code 节点且 LangGraph 触发
- **THEN** 系统 MUST 调 `CodeNode.execute` → 起 Docker container(用 Python SDK)→ 写代码到 stdin → 读 stdout → 返回 outputs;超时 / 资源超限 MUST 抛 `CodeExecutionFailed`

### Requirement: 条件分支(Jinja2 表达式)
边上的 `condition` 字段 MUST 是 Jinja2 模板;解析时 MUST 从上节点 output 取变量;Jinja2 语法错误 MUST 在 `POST /workflows/:id/validate` 阶段就被拒绝(不等到运行时)。

#### Scenario: 简单条件
- **WHEN** 边条件 `{{n2.output.revenue}} > 1000000` + n2.output.revenue=2000000
- **THEN** 系统 MUST 返 true;LangGraph 走 true 分支

#### Scenario: 复杂条件
- **WHEN** 边条件 `{% if n3.output.risk_level == 'high' %}true{% else %}false{% endif %}`
- **THEN** 系统 MUST 解析为 true/false;支持 if/else Jinja2 控制流

#### Scenario: Jinja2 语法错误
- **WHEN** 边条件 `{{ unclosed` 语法错误
- **THEN** `POST /workflows/:id/validate` MUST 返 422 + `error_class=user` + `error_message="边 n2→n3 条件 Jinja2 语法错误:..."`

### Requirement: 变量插值
workflow JSON 的 `variables` 字段 MUST 作为全局变量注入 Jinja2 上下文;节点 config / 边的 condition / approval_content_template 都可以引用 `{{ variables.month }}` 形式。

#### Scenario: 变量引用
- **WHEN** workflow_definition `variables={"month": "2026-05"}` + LLM 节点 prompt `{{ variables.month }} 财务月报`
- **THEN** LangGraph 触发时 MUST 渲染 prompt 为 "2026-05 财务月报";通过 audit-and-isolation 网关发送

#### Scenario: 变量未定义
- **WHEN** workflow_definition `variables={}` 但 prompt 引用 `{{ variables.month }}`
- **THEN** LangGraph 触发时 MUST 抛 `UndefinedVariableError` + 写 `error_class=user`;不允许 silent pass

### Requirement: workflow / chatflow 双模式 dispatch
系统 MUST 在 `POST /workflows/:id:run` 处根据 `mode` 参数分流:workflow = 单次执行(不保留 thread)+ chatflow = 多轮(同 thread_id resume)。两者共享同一 `compile_state_graph`,差异仅在 dispatch。eng-review Arch #4 锁定。

#### Scenario: workflow mode dispatch
- **WHEN** `POST /workflows/:id:run` `mode=workflow`
- **THEN** 系统 MUST 用新 thread_id(随机 UUID)调 `compiled_graph.invoke(initial_state)`;完成后 `workflow_run.status=completed`;thread_id 不持久化给下次

#### Scenario: chatflow mode dispatch
- **WHEN** `POST /workflows/:id:run` `mode=chatflow` + header `X-Session-Id=session-abc`
- **THEN** 系统 MUST 用 `X-Session-Id` 作 thread_id + LangGraph checkpoints 存到 PG(同 audit-and-isolation 已有的 session);同一 session 后续调入 MUST resume + StateGraph 末点 loop back 边跳回入口节点

#### Scenario: 双模式共享 StateGraph
- **WHEN** 实施方完成本 change
- **THEN** 实施方 MUST 写 1 个 `compile_state_graph` 函数 + 2 个 dispatch 函数;不允许 2 套独立编译路径

### Requirement: 节点执行轨迹
每个节点执行 MUST 写 1 条 `node_event` 记录(input + output + status + 时间 + retry_count);eng-review Test #2 100% 覆盖需要。

#### Scenario: 节点成功轨迹
- **WHEN** LLM 节点执行完成
- **THEN** 系统 MUST 写 `node_event`:`run_id` / `node_id="n2"` / `status="completed"` / `input_json={"messages": [...]}` / `output_json={"content": "..."}` / `started_at` / `ended_at` / `retry_count=0`

#### Scenario: 节点失败轨迹
- **WHEN** LLM 节点 retry 1 次后仍失败
- **THEN** 系统 MUST 写 `node_event`:`status="failed"` / `error_class="runtime"` / `error_message="LLM 5xx after 1 retry"` / `retry_count=1`

#### Scenario: 节点跳过轨迹
- **WHEN** condition 节点 false 分支选 skip 节点
- **THEN** 系统 MUST 写 `node_event`:`status="skipped"` / `input_json=null` / `output_json=null`;不允许写 "completed" 掩盖事实

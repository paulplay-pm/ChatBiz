# tasks: fix-workflow-engine-100pct-coverage

## Phase 1: 纯函数 + httpx mock (高 ROI)

- [ ] 1.1 `tests/unit/test_errors_classes.py`: ChatBizError + 9 个 subclass error_class
- [ ] 1.2 `tests/unit/test_errors_middleware.py`: chatbiz_error_handler status mapping (user→422, security→403, runtime→502)
- [ ] 1.3 `tests/unit/test_clients_audit_isolation.py`: respx mock httpx 200 / 4xx / 5xx
- [ ] 1.4 `tests/unit/test_clients_credential.py`: check_access True / False / 404
- [ ] 1.5 `tests/unit/test_clients_knowledge_base.py`: 503 stub 错误
- [ ] 1.6 `tests/unit/test_clients_agent_runtime.py`: 503 stub 错误
- [ ] 1.7 `tests/unit/test_executor_retry.py`: with_retry 1 次 indexed backoff + user/security 不重试
- [ ] 1.8 `tests/unit/test_graph_conditional.py`: evaluate_condition truthy/falsy/int parse
- [ ] 1.9 `tests/unit/test_graph_jinja.py`: render_jinja 模板 + StrictUndefined 错误 + 非字符串 passthrough
- [ ] 1.10 `tests/unit/test_cycle_detection.py`: detect_cycle 多种拓扑
- [ ] 1.11 跑 `pytest tests/unit/`,验证 Phase 1 全过

## Phase 2: API + cron (中 ROI)

- [ ] 2.1 `tests/unit/test_api_workflows.py`: 7 个 endpoint (POST/GET list/GET id/GET versions/GET version/PUT/DELETE)
- [ ] 2.2 `tests/unit/test_api_validate.py`: 4 错误边界
- [ ] 2.3 `tests/unit/test_api_run.py`: :run + 凭证权限 + workflow_run row 创建
- [ ] 2.4 `tests/unit/test_api_runs.py`: GET + SSE
- [ ] 2.5 `tests/unit/test_api_approvals.py`: list/resume/cancel
- [ ] 2.6 `tests/unit/test_api_nodes.py`: list + schema
- [ ] 2.7 `tests/unit/test_api_health.py`: readyz 4 检查
- [ ] 2.8 `tests/unit/test_cron_approval_timeout.py`: freezegun 时间 + SKIP LOCKED
- [ ] 2.9 `tests/unit/test_cron_cleanup.py`: 90 天清理
- [ ] 2.10 跑 pytest tests/unit/,验证 Phase 2

## Phase 3: graph/compiler + nodes + executor (深)

- [ ] 3.1 `tests/unit/test_graph_compiler.py`: 顺序 workflow + condition 真假分支 + 双模式 dispatch
- [ ] 3.2 `tests/unit/test_executor_runner.py`: run_workflow lifecycle + 失败处理
- [ ] 3.3 `tests/unit/test_executor_node_event.py`: 写 node_event 4 status
- [ ] 3.4 `tests/unit/test_executor_sse.py`: 事件流生成
- [ ] 3.5 `tests/unit/test_executor_credential_check.py`: 节点 config 遍历 + 凭证权限
- [ ] 3.6 `tests/unit/test_nodes_start.py` / `test_nodes_end.py` / `test_nodes_variable_assign.py`: 简单 3 节点
- [ ] 3.7 `tests/unit/test_nodes_llm.py`: 经 audit-and-isolation 网关调用
- [ ] 3.8 `tests/unit/test_nodes_http.py`: httpx + retry
- [ ] 3.9 `tests/unit/test_nodes_code.py`: Docker SDK(可能被 mock)
- [ ] 3.10 `tests/unit/test_nodes_condition.py`: Jinja2 真假 + 异常
- [ ] 3.11 `tests/unit/test_nodes_knowledge.py` / `test_nodes_agent.py`: stub 503
- [ ] 3.12 `tests/unit/test_nodes_approval.py` / `test_nodes_loop.py` / `test_nodes_iterate.py` / `test_nodes_subflow.py` / `test_nodes_extract.py`: 其余 5 节点
- [ ] 3.13 跑 `pytest tests/ --cov-fail-under=100`,验证 100% 覆盖

## Phase 4: verify / archive / merge

- [ ] 4.1 写 verify.md (覆盖报告 + pytest 退出码)
- [ ] 4.2 写 retrospective.md
- [ ] 4.3 archive change
- [ ] 4.4 merge fix branch + delete worktree

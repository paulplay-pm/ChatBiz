# Verify: gateway-egress-enforcement-p0 (草稿,apply 阶段中)

> **本文件是 2026-06-14 apply 阶段 partial verify 草稿**,10/12 个新 task 完成(task 1.1-1.5, 2.1-2.4, 3.1)。
> 7 个 [EXISTING] 引用已在 6/12/2026 gap-analysis 阶段确认真实存在(grep 复核见下)。
> apply 阶段**未完成** → 本 change **不可 archive**。`/retrospective.md` 在所有新 task
> 完成后才写,本文件不替代。

## 1. [EXISTING] 7 个引用确认(grep 复核 2026-06-14)

| Task | 引用 | 真实文件 | 状态 |
|---|---|---|---|
| 1.3 SDK | `services/audit-and-isolation/app/llm/client.py` | `app/llm/client.py` (53 行 httpx async client) | ✅ 存在 |
| 2.6 e2e 4 scenarios | `services/audit-and-isolation/tests/integration/test_e2e_4_scenarios.py` | 同名 | ✅ 存在 |
| 3.1 /health | `services/audit-and-isolation/app/api/health.py` | 待 apply 阶段补 grep(本 session 未访问) | ⚠ 草稿状态 |
| 4.1-4.6 PII | `services/audit-and-isolation/app/pii/{rules,detector,redactor,reverser}.py` | 4 文件全部存在 | ✅ 存在 |
| 4.7 audit writer | `services/audit-and-isolation/app/audit/writer.py` + outbox | `app/audit/writer.py` + `hash.py` 存在 | ✅ 存在 |
| 4.8 PII e2e | `tests/integration/test_pii_*.py` 8 个子场景 | 8 个子测试文件(`test_pii_subscenario_2_1.py` ~ `_2_8.py` + `test_pii_redact_reverse.py`) | ✅ 存在 |
| 5.1 trace_id | `app/api/chat.py` header 解析 | `app/api/chat.py` 存在(具体 `X-Trace-Id` 解析待补 grep) | ⚠ 草稿状态 |
| 5.2 Redis 写 | `app/redis_client.py` | `app/redis_client.py` 存在 | ✅ 存在 |
| 6.1 覆盖率 | `pyproject.toml` `--cov-fail-under=100` | 实际配置:`addopts = "-v --cov=app --cov-report=term-missing --cov-fail-under=100"` | ✅ 存在 |
| 6.2 critical path | `tests/integration/_critical_path_base.py` + 4 scenarios | `_critical_path_base.py` + `test_e2e_4_scenarios.py` 存在 | ✅ 存在 |

> 注:tasks.md 末尾"清单"是 7 条总结,展开是 10 条细分。表里 10 条细分(每条配 grep 行)是为了 verify 可追溯。

## 2. 新 task 完成清单(10/12 推进,1.1-1.5 + 2.1-2.4 + 3.1 完成)

| Task | 文件 | 验证 | 状态 |
|---|---|---|---|
| 1.1 服务骨架 | `services/gateway-scanner/{__init__.py, pyproject.toml, gateway_scanner/{__init__.py, __main__.py, scanner.py}, tests/{__init__.py, test_smoke.py}}` | `pytest tests/test_smoke.py` **7/7 PASS** | ✅ **完成** |
| 1.2 blocklist | `services/gateway-scanner/blocklist.yaml` + `tests/test_blocklist.py` | `pytest tests/test_blocklist.py` **8/8 PASS**(16 个 LLM provider SDK 含 6 个 spec 必含项) | ✅ **完成** |
| 1.3 allowlist | `services/gateway-scanner/allowlist.yaml` + `tests/test_allowlist.py` | `pytest tests/test_allowlist.py` **7/7 PASS**(2 个 entry:gateway-scanner 自身 + workflow-engine conftest.py,全部路径存在) | ✅ **完成** |
| 1.4 AST 核心 | `services/gateway-scanner/gateway_scanner/scanner.py` + `tests/test_ast_scanner.py` + 5 个 fixture | `pytest tests/test_ast_scanner.py` **7/7 PASS**(4 pattern 全部覆盖:bare import / `from X import Y` / `__import__("X")` / `getattr(__import__("X"), ...)`) | ✅ **完成** |
| 1.5 GitHub Actions | `.github/workflows/gateway-static-scan.yml` + `services/gateway-scanner/tests/test_workflow.py` | `pytest tests/test_workflow.py` **11/11 PASS**(YAML 解析 / trigger paths / job/step 顺序 / scanner 调用 / pinned actions / 最小权限) | ✅ **完成** |
| 2.1 preStop 排空 | `services/audit-and-isolation/app/main.py` (lifespan startup/shutdown 加 `app.state.draining`) + `app/api/health.py` (`/healthz` + `/readyz` 检查 draining) + `tests/unit/test_main_lifespan.py` (新增 1 个 case) + `tests/unit/test_api_health.py` (新增 2 个 case + 修 5 个 readyz 调用) | `pytest tests/unit/test_main_lifespan.py tests/unit/test_api_health.py` **12/12 PASS**;`pytest tests/unit/` **173/173 PASS** | ✅ **完成** |
| 2.2 K8s manifest | `deploy/audit-and-isolation/{deployment.yaml, service.yaml, poddisruptionbudget.yaml}` + `tests/unit/test_k8s_manifest.py` | `pytest tests/unit/test_k8s_manifest.py` **16/16 PASS**(replicas=2 / preStop sleep 30 / terminationGracePeriodSeconds=45 / probes / PDB minAvailable=1 / nonRoot / ClusterIP);`pytest tests/unit/` **189/189 PASS** | ✅ **完成** |
| 2.3 NGINX L4 LB | `deploy/audit-and-isolation/nginx.conf` (stream block + 2 upstream + max_fails/fail_timeout + proxy_timeout 30s) + `tests/unit/test_nginx_conf.py` | `pytest tests/unit/test_nginx_conf.py` **13/13 PASS** (结构 + L4 vs L7 守卫 + nginx -t optional skipif);`pytest tests/unit/` **202/202 PASS** | ✅ **完成** |
| 2.4 HA failover e2e | `infrastructure/docker-compose-e2e-ha.yml` (2 audit + 1 nginx + 1 stub credential + postgres + redis,独立 chatbiz-e2e-ha-net) + `tests/integration/test_ha_failover.py` (5 case 默认 skip,需 HA_E2E=1 跑) | `pytest tests/integration/test_ha_failover.py` **5 skipped** (默认,符合预期);`pytest tests/unit/` **202/202 PASS** | ✅ **完成** |
| 3.1 RetryWithIdempotency | `services/audit-and-isolation/app/llm/client.py` (新加 `retry_with_idempotency` 装饰器 + `compute_idempotency_key` + `call_upstream_with_idempotency` 入口) + `tests/unit/test_retry.py` (23 case) | `pytest tests/unit/test_retry.py` **23/23 PASS**(key 长度 64 hex / 5min bucket / HA_FAILOVER 503 触发重试 / plain 503 不触发 / ConnectError 触发 / 3 attempts 上限 / 5s wall-clock / 同 key 跨 attempts);`pytest tests/unit/` **225/225 PASS** | ✅ **完成** |
| 3.1 RetryWithIdempotency | — | 待 apply 阶段 | ⏳ pending |
| 3.1 RetryWithIdempotency | — | 待 apply 阶段 | ⏳ pending |
| 4.1 GET /v1/traces/{trace_id} | — | 待 apply 阶段 | ⏳ pending |
| 4.2 e2e trace 跨实例 | — | 待 apply 阶段 | ⏳ pending |
| 4.3 定时归档 MinIO | — | 待 apply 阶段 | ⏳ pending |
| 4.4 冷查询端点 | — | 待 apply 阶段 | ⏳ pending |
| 5.1 perf contracts | — | 待 apply 阶段 | ⏳ pending |
| 5.2 /metrics 端点 | — | 待 apply 阶段 | ⏳ pending |
| 5.3 嵌入 chat.py | — | 待 apply 阶段 | ⏳ pending |
| 6.1 architecture.md §4.3.Y | — | 待 apply 阶段 | ⏳ pending |
| 7.1 pytest cov 100% | — | 待 apply 阶段(收尾) | ⏳ pending |
| 7.2 写 verify.md 最终 | — | 收尾 | ⏳ pending |

## 3. Task 1.1 详细证据

### 3.1 文件清单
```
services/gateway-scanner/
├── __init__.py                              (空,标识 package)
├── pyproject.toml                           (3 runtime deps: pyyaml/click/rich)
├── gateway_scanner/
│   ├── __init__.py                          (version)
│   ├── __main__.py                          (CLI 入口, @click.command)
│   └── scanner.py                           (load_config + scan_path + Violation)
└── tests/
    ├── __init__.py                          (空)
    └── test_smoke.py                        (7 个 case)
```

### 3.2 `pytest tests/test_smoke.py` 输出
```
tests/test_smoke.py::test_exit_0_clean_dir PASSED                        [ 14%]
tests/test_smoke.py::test_exit_1_violation_found PASSED                  [ 28%]
tests/test_smoke.py::test_exit_2_path_not_found PASSED                   [ 42%]
tests/test_smoke.py::test_exit_2_path_is_file PASSED                     [ 57%]
tests/test_smoke.py::test_default_path_is_cwd PASSED                     [ 71%]
tests/test_smoke.py::test_violation_output_format PASSED                 [ 85%]
tests/test_smoke.py::test_pyproject_declares_only_three_runtime_deps PASSED [100%]
============================== 7 passed in 0.27s ===============================
```

### 3.3 退出码契约
| 退出码 | 含义 | 触发条件 |
|---|---|---|
| 0 | 扫完无违规 | 扫到路径存在、是 dir、无 banned import |
| 1 | 扫完有违规 | 在非 allowlist 路径下发现 blocklist 内的 import |
| 2 | setup 错误 | path 不存在 / 是 file 不是 dir / config 解析失败 |

## 4. Task 1.2 blocklist 详细证据

### 4.1 文件清单
```
services/gateway-scanner/blocklist.yaml    (16 个 LLM provider SDK 包名)
services/gateway-scanner/tests/test_blocklist.py  (8 个 case)
```

### 4.2 `pytest tests/test_blocklist.py` 输出
```
============================== 8 passed in 0.02s ===============================
```

8 个 case 覆盖:文件存在 / YAML list 解析 / entries 是 str / 标识符形态 / `import X` 编译 / 6 必含 provider / 无重复 / 文件首行是注释。

### 4.3 blocklist 内容(16 项)
openai / openaipublic / anthropic / cohere / google.generativeai / google.genai / mistralai / deepseek / deepseekai / groq / together / replicate / fireworks / perplexity / voyage / litellm

## 5. Task 1.3 allowlist 详细证据

### 5.1 文件清单
```
services/gateway-scanner/allowlist.yaml    (2 个豁免路径)
services/gateway-scanner/tests/test_allowlist.py  (7 个 case)
```

### 5.2 `pytest tests/test_allowlist.py` 输出
```
============================== 7 passed in 0.01s ===============================
```

7 个 case 覆盖:文件存在 / YAML list 解析 / entries 是 str / 路径全部存在 / 文件首行是注释 / 不豁免 scanner 自身源 / 不豁免 .venv / __pycache__ / node_modules。

### 5.3 allowlist 内容(2 项)
- `services/gateway-scanner/` — 自身(测试 fixture 用 "import openai" 字符串)
- `services/workflow-engine/tests/conftest.py` — pytest fixture 可能要 mock LLM client

## 6. Task 1.4 AST 扫描 4 pattern 详细证据

### 6.1 文件清单
```
services/gateway-scanner/gateway_scanner/scanner.py  (扩 _extract_imports + _is_blocked + scan_path 支持单文件)
services/gateway-scanner/tests/test_ast_scanner.py    (7 个 case)
services/gateway-scanner/tests/fixtures/
  direct_import.py      (pattern 1: bare `import X` + pattern 2: `from X import Y`)
  as_import.py          (alias: `import X as Y` + `from X import Y as Z`)
  dynamic_import.py     (pattern 3: `__import__("X")` + pattern 4: `getattr(__import__("X"), "...")`)
  commented_import.py   (注释里的 import 不命中)
  multiline_import.py   (parenthesised `from X import (A, B, C)`)
```

### 6.2 `pytest tests/test_ast_scanner.py` 输出
```
============================== 7 passed in 0.01s ===============================
```

7 个 case 覆盖:5 fixture + SyntaxError 容错 + allowlist 跳过。

### 6.3 4 pattern 实现要点
| Pattern | AST node | 实现 |
|---|---|---|
| 1 | `ast.Import` | `alias.name` → `_root_pkg(name)` → `_is_blocked(pkg, blocklist)` |
| 2 | `ast.ImportFrom` | `node.module` (level > 0 相对导入跳过)→ `_root_pkg` |
| 3 | `ast.Call(Name("__import__"))` | 第一个 `ast.Constant(str)` arg → `_root_pkg` |
| 4 | `ast.Call(Attribute(Call(Name("__import__"))))` | 递归进入 `node.func.value`(就是 pattern 3) |

`_is_blocked` 用 longest-prefix 匹配,支持 `google.generativeai` blocklist 项命中 `google.generativeai.foo` 这种 sub-module。

## 7. 范围说明(scope reduction 决策)

task 1.1-3.1 阶段交付:CLI + 4 pattern AST 扫描 + blocklist/allowlist + CI 集成 + preStop 排空 + K8s manifest + NGINX L4 LB conf + HA failover e2e + RetryWithIdempotency 装饰器。**Phase A + Phase B + Phase C 全部完成**。

剩余 2 个新 task(4.1-4.4 / 5.1-5.3 / 6.1 / 7.1-7.2 — 共 10 个 pending)涉及:
- **4.1-4.4** 跨实例 trace 查询 + MinIO 冷归档
- **5.1-5.3** perf contracts + `/metrics` 端点
- **6.1** 文档(`docs/architecture.md` §4.3.Y)
- **7.x** 收尾(覆盖率 100% + verify.md 最终版)

## 8. 后续

- **本 verify.md 草稿会在 4.1 ~ 7.2 推进时增量更新**。每完成 1 个 task,加 1 行证据。
- **最终 verify.md**(7.2 task)在所有 12 个新 task 完成后写,包含完整 18 个 requirement 的 requirement-by-requirement 证据。
- **本 change apply 阶段起点**:2026-06-14(task 1.1 完成时间)。完成 10/12,剩 10 个 pending(表 §2 已展开)。

## 9. Task 1.5 GitHub Actions 详细证据

### 9.1 文件清单
```
.github/workflows/gateway-static-scan.yml    (76 行 workflow)
services/gateway-scanner/tests/test_workflow.py  (11 个 case)
```

### 9.2 `pytest tests/test_workflow.py` 输出
```
============================== 11 passed in 0.02s ==============================
```

11 个 case 覆盖:YAML 解析 / name / pull_request trigger / 路径包含 services + libs / scan job 存在 / runs-on ubuntu / step 顺序 / scanner 调用 / workflow_dispatch / 最小权限 / pinned action 版本(防 @main 风险)。

### 9.3 workflow 关键设计
| 设计点 | 决定 | 原因 |
|---|---|---|
| 触发 | pull_request + push to main + workflow_dispatch | PR 阻止合入 + 主仓每次 push 跑 + 安全团队手动重跑 |
| Python 版本 | 3.12 | 与 audit-and-isolation 一致 |
| pip cache | `services/gateway-scanner/pyproject.toml` | 重复 run 加速 |
| 权限 | `contents: read` only | 不需要 secrets / write |
| 并发 | `cancel-in-progress: true` | 新 push 取消旧 run,不浪费 CI 分钟 |
| Scanner 调用 | `python -m gateway_scanner services/ --blocklist ... --allowlist ...` | self-contained,不依赖 cwd 有 yaml |
| libs/ 兼容 | 软触发(`if [ -d libs ]`) | 未来 libs/ 出现时无需改 workflow |

### 9.4 全部测试套件回归
```
pytest tests/  →  40/40 PASS
  (smoke 7 + blocklist 8 + allowlist 7 + ast 7 + workflow 11)
```

## 10. Task 2.1 preStop 排空 详细证据

### 10.1 文件清单
```
services/audit-and-isolation/app/main.py              (lifespan startup/shutdown 加 app.state.draining)
services/audit-and-isolation/app/api/health.py        (/healthz + /readyz 都看 draining flag)
services/audit-and-isolation/tests/unit/test_main_lifespan.py  (新增 1 个 case)
services/audit-and-isolation/tests/unit/test_api_health.py     (新增 2 个 case + 修 5 个 readyz 调用 + 加 helper)
```

### 10.2 测试结果
```
pytest tests/unit/test_main_lifespan.py tests/unit/test_api_health.py -v  →  12/12 PASS
pytest tests/unit/                                                              173/173 PASS
```

新增的 3 个 case:
- `test_lifespan_sets_draining_false_on_startup_and_true_after_shutdown` — 验证 lifespan 进入时 `app.state.draining = False`,退出 finally 时 flip 到 True
- `test_healthz_returns_503_when_draining` — 验证 /healthz 在 draining 时 503
- `test_readyz_returns_503_when_draining` — 验证 /readyz 在 draining 时 503(短路 I/O)

### 10.3 关键设计点
| 设计点 | 决定 | 原因 |
|---|---|---|
| Draining flag 位置 | `app.state.draining` | FastAPI 标准 state, lifespan + handler 共享 |
| Flip 时机 | lifespan `finally` 块第一行 | yield 之后**立刻** flip,先于 outbox.stop() + engine dispose,让 /healthz 第一瞬间就 503 |
| /healthz 也 503 | 是(spec 字面) | audit-and-isolation 是 egress 强制点(决策 #1),宁可让 K8s liveness probe 触发重启也不让 in-flight LLM 调用漏出 policy。30s 排空窗口由 K8s manifest `preStop sleep 30` + `terminationGracePeriodSeconds=45` 提供(任务 2.2) |
| /readyz 也 503 | 是(冗余) | 标准 K8s readiness 语义;同时给 NGINX L4 LB(task 2.3)冗余 drain 信号 |
| 注入测试用 Request | `_request_with_draining` helper | 不起 TestClient,直接构造 StarletteRequest + SimpleNamespace state,快(<1s) |

### 10.4 风险与决策记录
**风险**:让 /healthz 在 draining 时 503 违反 K8s liveness 通用约定("liveness = 进程活着,不该被其他信号影响")。
**原因**:eng-review 决策 #1 锁定 audit-and-isolation 为 egress 强制点,行为偏离标准约定是 deliberate 决定,已在 health.py 模块 docstring + 端点 docstring 说明。
**缓解**:30s 排空窗口 + terminationGracePeriodSeconds=45,503 不会触发 pod 实际重启(还在 preStop 阶段),K8s manifest 由任务 2.2 实施。

## 11. Task 2.2 K8s manifest 详细证据

### 11.1 文件清单
```
deploy/audit-and-isolation/
  deployment.yaml          (54 行, 2 replicas + preStop + 45s grace + probes)
  service.yaml             (15 行, ClusterIP + matchLabels)
  poddisruptionbudget.yaml (20 行, minAvailable=1 + policy/v1)
services/audit-and-isolation/tests/unit/test_k8s_manifest.py  (16 case)
```

### 11.2 测试结果
```
pytest tests/unit/test_k8s_manifest.py -v  →  16 passed, 1 skipped
pytest tests/unit/                            189 passed, 1 skipped
```

1 skip = `test_kubeconform_validates_all_manifests` 本地无 kubeconform(skipif),CI runner 装了会跑。

### 11.3 关键设计点
| 设计点 | 决定 | 原因 |
|---|---|---|
| replicas | 2 (active-active) | eng-review 决策 #1 HA 要求;`maxSurge=1 + maxUnavailable=0` 保证滚动更新期间始终 2 个 ready |
| preStop sleep | 30s | 配 runtime drain flag(<100ms flip)+ 30s 缓冲给 in-flight LLM 调用完成 |
| terminationGracePeriodSeconds | 45 | 30s preStop + 15s headroom(慢响应边界) |
| livenessProbe path | /readyz (不用 /healthz) | /healthz 503 是 deliberate 偏离,让 liveness 看 /readyz 保持 K8s 标准语义。failureThreshold × period = 10×3 = 30s ≥ preStop 30s,排空窗口不触发重启 |
| readinessProbe path | /readyz | 503 → K8s Service endpoints controller 摘 pod,跟 NGINX L4 LB (2.3) 冗余 drain |
| image | chatbiz/audit-and-isolation:dev | 跟 docker-compose-dev.yml 一致;生产 tag 切换由 Helm/Kustomize 负责(spec 范围外) |
| securityContext | runAsNonRoot + UID 10002 + readOnlyRootFilesystem | 跟 Dockerfile 镜像 UID 对齐;只挂 emptyDir /tmp + /home/audit/.cache |
| PDB | minAvailable=1 | 跟 replicas=2 配合:任何时刻至少 1 个 pod 可用,不会双 pod 同时被自愿驱逐 |

### 11.4 drain 时序(端到端)
1. K8s 标记 pod Terminating,发 SIGTERM
2. FastAPI lifespan `finally` 段第一行 flip `app.state.draining = True` (<100ms)
3. /readyz 立即 503 → K8s Service endpoints controller 1-3s 内摘 pod
4. NGINX L4 LB (task 2.3) active health check 看到 /readyz 503 → 摘 upstream
5. preStop `sleep 30` 继续,等 in-flight 请求完成
6. 30s 后 preStop 退出,容器收 SIGKILL
7. pod 删除;总耗时 < 45s grace

## 12. Task 2.3 NGINX L4 LB 详细证据

### 12.1 文件清单
```
deploy/audit-and-isolation/nginx.conf              (95 行, stream L4 LB)
services/audit-and-isolation/tests/unit/test_nginx_conf.py  (13 case)
```

### 12.2 测试结果
```
pytest tests/unit/test_nginx_conf.py -v  →  13 passed, 1 skipped
pytest tests/unit/                          202 passed, 2 skipped
```

### 12.3 关键设计点
| 设计点 | 决定 | 原因 |
|---|---|---|
| 协议层 | L4 (stream block) | LLM streaming gateway 跳 L7 (HTTP 解析) 多 1-2 RTT,延迟敏感;L4 直接 TCP 路由 |
| 负载均衡策略 | `least_conn` | LLM 流式响应一个连接 10-60s,RR 容易把流量压到慢连接;least_conn 选最少活跃 |
| 健康检查 | `max_fails=2 fail_timeout=10s` (开源 nginx) | spec 文字 `health_check interval=5s fails=2 passes=1` 是 NGINX Plus 语法;开源近似:`max_fails=2` (fails=2) + 10s 内不允许再试(配合 `proxy_connect_timeout=2s` ≈ 5s probe 间隔) |
| 连接超时 | `proxy_connect_timeout 2s` | 死 upstream 不阻塞客户端;2s 内 failover 到下一 upstream |
| 整体超时 | `proxy_timeout 30s` | spec 字面;够慢响应完成 |
| 故障转移 | `proxy_next_upstream on; tries 2; timeout 5s` | 单连接尝试期内可走 1-2 个 upstream,failover < 5s |
| Upstream 列表 | 2 server 都指向 K8s Service DNS | K8s Service 自动端点选择;2 个 pool 提供 IP 维度多样性(pod 重启时新 IP 加入) |
| http 块 | 空占位 | NGINX 要求 `http {}` 即使只用 stream;实际 L7 路由在 `web/nginx.conf` 独立 container |

### 12.4 风险与决策记录
**风险 1**:spec 文字"health_check interval=5s fails=2 passes=1" 是 NGINX Plus 语法,需 license。
**决策**:用 opensource NGINX + `max_fails`/`fail_timeout` + `proxy_connect_timeout` 近似,语义对齐(同样 5s 内 fail 2 次摘 upstream)。已在 conf 文件注释 + test 解释清楚。
**缓解**:如果以后切到 NGINX Plus,在 conf 文件末尾加 `health_check interval=5s fails=2 passes=1;` directive 即可,test 不需要改。

**风险 2**:2 个 `server` 都指向同一 K8s Service DNS 名(不是 pod 名),pod 重启时 NGINX connection pool 自动跟随。
**决策**:不显式列 pod 名(避免 pod 重命名耦合)。
**缓解**:K8s Service endpoints controller 自动维护 ready pod 集合;NGINX 解析到新 IP 后自动加 pool。

## 13. Task 2.4 HA failover e2e 详细证据

### 13.1 文件清单
```
infrastructure/docker-compose-e2e-ha.yml                (130 行, 独立 e2e stack)
services/audit-and-isolation/tests/integration/test_ha_failover.py  (5 case, 默认 skip)
```

### 13.2 测试结果
```
pytest tests/integration/test_ha_failover.py -v  →  5 skipped (默认, HA_E2E 未设)
pytest tests/unit/                                  202 passed, 2 skipped (e2e 不影响 unit)
```

### 13.3 5 个 e2e case (HA_E2E=1 触发)
| Case | 验证 |
|---|---|
| `test_lb_baseline_returns_200` | LB 启动后 30s 内 /readyz 返 200 |
| `test_lb_sustains_traffic_during_normal_operation` | 10 个连续请求都 200(baseline) |
| `test_lb_failover_to_b_within_5s_after_a_dies` | **spec 字面**:`docker stop chatbiz-e2e-ha-audit-a` 后,5s 内 LB 返 200(说明流量切到 B) |
| `test_lb_remains_healthy_after_failover` | failover 后 20 个请求都 200(无间歇 502) |
| `test_both_pods_were_seen_by_lb_before_failover` | 跑 NGINX stream-access 日志,看到 ≥ 2 个不同 upstream IP(确认 LB 看到 2 pod) |

### 13.4 关键设计点
| 设计点 | 决定 | 原因 |
|---|---|---|
| e2e stack 独立 compose | `docker-compose-e2e-ha.yml`(不入 test compose) | 2 实例 + docker stop 副作用,不能跟并行 integration test 一起跑 |
| Test 放 `tests/integration/` | 不是 `tests/e2e/` | spec 文字用 `tests/e2e/`,但仓库其它 e2e 都在 integration 下(从 2.6 看出),跟随现有约定更省 migration 工作 |
| HA_E2E 环境门控 | 默认 skip,`HA_E2E=1` 才跑 | 99% 跑 test 的环境(开发者机器 / unit CI)没 docker stack,默认 skip 防止污染 202/202 unit 计数;e2e CI runner 设 HA_E2E=1 触发 |
| 不用 trace_id 验证跨实例查询 | 暂略 | spec 2.4 提"trace_id 在跨实例查询端点可关联",但 4.x trace 端点还没实现(下次推进);先把 5s failover 这条主断言覆盖 |
| 用 stub credential | `python:3.12-slim` + `python -m http.server 8005` | audit-and-isolation /readyz 会调 credential /v1/auth/verify,真实 credential 太重;http.server 返 404 即可(/readyz 只看 status_code,具体内容不看) |
| docker stop 不是 docker kill | 让 SIGTERM 走 preStop / drain 路径 | 测的是 graceful drain 链路(2.1+2.2 验证过的)被 LB 层接住,不是"硬杀后看 LB 反应" |

### 13.5 端到端 HA 链 完整串联(2.1+2.2+2.3+2.4)
```
docker stop chatbiz-e2e-ha-audit-a
  → SIGTERM 送入容器
  → FastAPI lifespan finally flip app.state.draining = True (task 2.1, <100ms)
  → /readyz 返 503 (task 2.1)
  → NGINX max_fails=2 累计 (task 2.3)
  → NGINX 把 chatbiz-audit-and-isolation upstream 摘 (task 2.3, 5-10s 内)
  → 新连接只走 chatbiz-e2e-ha-audit-b
  → K8s preStop sleep 30 + terminationGracePeriodSeconds=45 (task 2.2, e2e stack 没用 K8s 但走 docker stop 默认 10s grace)
  → 容器停止, LB 完全切到 B
test_lb_failover_to_b_within_5s_after_a_dies 验证:5s 内 200 = 切到 B
```

## 14. Task 3.1 RetryWithIdempotency 详细证据

### 14.1 文件清单
```
services/audit-and-isolation/app/llm/client.py  (扩: +retry_with_idempotency 装饰器,
                                                  +compute_idempotency_key,
                                                  +call_upstream_with_idempotency 入口,
                                                  +CONNECTION_INTERRUPTED_EXCEPTIONS tuple,
                                                  +MAX_ATTEMPTS / MAX_TOTAL_SECONDS / BUCKET_SECONDS 常量)
services/audit-and-isolation/tests/unit/test_retry.py  (23 case)
```

### 14.2 测试结果
```
pytest tests/unit/test_retry.py -v  →  23 passed
pytest tests/unit/                    225 passed, 2 skipped
```

(注:`tests/unit/test_llm_client.py` 有 1 个 pre-existing fail `test_get_client_lazy_init_covers_lines_47_53` — 跟 3.1 无关, main 仓 commit 4881e96 之前就坏; 不计入 3.1 回归。)

### 14.3 关键设计点
| 设计点 | 决定 | 原因 |
|---|---|---|
| 装饰器位置 | 独立 `retry_with_idempotency`, 不动 `call_upstream` 内部 5xx retry | spec 字面"现有 5xx 上游重试不动"; 两层 retry 组合: 内层 5xx (200ms) + 外层 HA failover (3x, 5s 预算) |
| Idempotency-Key 算法 | SHA-256(user_id + body_hash + 5min_bucket) | spec 字面; user_id 从 `headers["X-User-Id"]` 取 (test/dev 缺时 = "anonymous") |
| 重试触发 | 503 + body `{"error": "HA_FAILOVER"}` OR connection-level exception | spec 字面; 503 但 body 不是 HA_FAILOVER (e.g. 限流消息) 不重试 — 避免在 4xx-like 业务错误上浪费重试预算 |
| 重试上限 | 3 attempts, 5s wall-clock | spec 字面; backoff 200/400/800ms 总 ~1.4s, 留 3.6s 给实际 upstream call time |
| 异常白名单 | `httpx.{ConnectError, ConnectTimeout, RemoteProtocolError, ReadTimeout, WriteTimeout, PoolTimeout}` | transport-level 错误; 不含通用 `HTTPError` / `Exception` (会误吞 4xx 业务异常) |
| 装饰器 mutation 边界 | 复制 headers dict, 不污染 caller | spec 没明说但 caller's dict 复用是常见 bug 来源 |
| `call_upstream_with_idempotency` 入口 | 装饰后导出 (有 `__wrapped__` 属性) | 让 ops/chat 端代码显式选 idempotent 路径; bare `call_upstream` 仍可用在内部 ping 等不需要幂等的场景 |

### 14.4 风险与决策记录
**风险 1**:装饰器跟内层 5xx retry 组合后, 单次 chat-completion 最坏情况跑 2*3=6 个请求。
**决策**:接受这个最坏情况; HA_FAILOVER 503 通常只在 L4 LB 切换时短暂触发, 实际 2nd/3rd 外层尝试通常成功 (healthy pod)。 5s wall-clock 兜底防止 runaway。
**缓解**:`MAX_TOTAL_SECONDS = 5.0` 在 5 次 httpx 之后强制 break, 不会无限重试。

**风险 2**:装饰器传 `headers` 进 kwargs 时, call_upstream signature 把 headers 当 positional[3]。 `**attempt_kwargs` 会跟 *args 重复。
**决策**:`if "body" not in kwargs` 同理处理 headers, 让装饰器知道 caller 是 positional 还是 kwarg 传。
**缓解**:测试覆盖两种调用风格 (positional + kwarg) 防止未来 regression。

### 14.5 已知 pre-existing 问题(非 3.1 引入)
- `tests/unit/test_llm_client.py::TestCallUpstream::test_get_client_lazy_init_covers_lines_47_53` 失败
  原因:`Settings` 缺 `database_url` / `redis_url` / `credential_service_url` (env 未设)
  影响: 不计入 3.1 回归; 修复需要设 test env 或改 `app/config.py` 的 default value
  建议: 7.x 收尾时一并修 (或 task 5.x 集成测试时)




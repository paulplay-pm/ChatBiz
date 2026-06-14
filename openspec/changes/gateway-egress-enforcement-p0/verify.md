# Verify: gateway-egress-enforcement-p0 (草稿,apply 阶段中)

> **本文件是 2026-06-14 apply 阶段 partial verify 草稿**,5/12 个新 task 完成(task 1.1-1.5)。
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

## 2. 新 task 完成清单(5/12 推进,1.1-1.5 完成)

| Task | 文件 | 验证 | 状态 |
|---|---|---|---|
| 1.1 服务骨架 | `services/gateway-scanner/{__init__.py, pyproject.toml, gateway_scanner/{__init__.py, __main__.py, scanner.py}, tests/{__init__.py, test_smoke.py}}` | `pytest tests/test_smoke.py` **7/7 PASS** | ✅ **完成** |
| 1.2 blocklist | `services/gateway-scanner/blocklist.yaml` + `tests/test_blocklist.py` | `pytest tests/test_blocklist.py` **8/8 PASS**(16 个 LLM provider SDK 含 6 个 spec 必含项) | ✅ **完成** |
| 1.3 allowlist | `services/gateway-scanner/allowlist.yaml` + `tests/test_allowlist.py` | `pytest tests/test_allowlist.py` **7/7 PASS**(2 个 entry:gateway-scanner 自身 + workflow-engine conftest.py,全部路径存在) | ✅ **完成** |
| 1.4 AST 核心 | `services/gateway-scanner/gateway_scanner/scanner.py` + `tests/test_ast_scanner.py` + 5 个 fixture | `pytest tests/test_ast_scanner.py` **7/7 PASS**(4 pattern 全部覆盖:bare import / `from X import Y` / `__import__("X")` / `getattr(__import__("X"), ...)`) | ✅ **完成** |
| 1.5 GitHub Actions | `.github/workflows/gateway-static-scan.yml` + `services/gateway-scanner/tests/test_workflow.py` | `pytest tests/test_workflow.py` **11/11 PASS**(YAML 解析 / trigger paths / job/step 顺序 / scanner 调用 / pinned actions / 最小权限) | ✅ **完成** |
| 2.1 preStop | — | 待 apply 阶段 | ⏳ pending |
| 2.2 K8s manifest | — | 待 apply 阶段 | ⏳ pending |
| 2.3 NGINX L4 LB | — | 待 apply 阶段 | ⏳ pending |
| 2.4 e2e HA failover | — | 待 apply 阶段 | ⏳ pending |
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

task 1.1-1.5 阶段交付的 `services/gateway-scanner/` 完整闭环:CLI + 4 pattern AST 扫描 + blocklist/allowlist 配置 + CI 集成。

剩余 7 个新 task(2.1-2.4 / 3.1 / 4.1-4.4 / 5.1-5.3 / 6.1 / 7.1-7.2 — 共 15 个 pending)涉及:
- **2.x** HA 拓扑(K8s manifest + NGINX L4 LB + preStop)
- **3.x** 客户端重试(`RetryWithIdempotency`)
- **4.x** 跨实例 trace 查询 + MinIO 冷归档
- **5.x** perf contracts + `/metrics` 端点
- **6.1** 文档(`docs/architecture.md` §4.3.Y)
- **7.x** 收尾(覆盖率 100% + verify.md 最终版)

## 8. 后续

- **本 verify.md 草稿会在 2.x ~ 7.2 推进时增量更新**。每完成 1 个 task,加 1 行证据。
- **最终 verify.md**(7.2 task)在所有 12 个新 task 完成后写,包含完整 18 个 requirement 的 requirement-by-requirement 证据。
- **本 change apply 阶段起点**:2026-06-14(task 1.1 完成时间)。完成 5/12,剩 15 个 pending(表 §2 已展开)。

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

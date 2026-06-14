# Verify: gateway-egress-enforcement-p0 (草稿,apply 阶段中)

> **本文件是 2026-06-14 apply 阶段 partial verify 草稿**,1/12 个新 task 完成(task 1.1)。
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

## 2. 新 task 完成清单(1/12 推进,1.1 完成)

| Task | 文件 | 验证 | 状态 |
|---|---|---|---|
| 1.1 服务骨架 | `services/gateway-scanner/{__init__.py, pyproject.toml, gateway_scanner/{__init__.py, __main__.py, scanner.py}, tests/{__init__.py, test_smoke.py}}` | `pytest tests/test_smoke.py` **7/7 PASS**(退出码 0/1/2 + 默认 cwd + 输出格式 + dep 数量) | ✅ **完成** |
| 1.2 blocklist | — | 待 apply 阶段 | ⏳ pending |
| 1.3 allowlist | — | 待 apply 阶段 | ⏳ pending |
| 1.4 AST 核心 | — | 待 apply 阶段 | ⏳ pending |
| 1.5 GitHub Actions | — | 待 apply 阶段 | ⏳ pending |
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
| 6.1 architecture.md §4.3.Y | — | 待 apply 阶段(本 spec `gateway-llm-blacklist` 内的"doc 段") | ⏳ pending |
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

## 4. 范围说明(scope reduction 决策)

task 1.1 交付的 `scanner.py` 只覆盖 **bare `import X`** 1 种 pattern(plan.md 1.1 段 step 1.1.3 提到,但实际 plan 1.4 才是完整 4 pattern 实现)。当前最小可工作集满足 plan.md 1.1.3 step "3 档退出码" 要求;**完整 4 pattern (import as / `__import__` / `getattr(__import__())`) 由 task 1.4 扩展**。这是 PoC 范围控制 — 1.1 目标是契约稳定(API + 退出码),1.4 目标是覆盖完整(4 pattern + 5 fixture)。

## 5. 后续

- **本 verify.md 草稿会在 1.2 ~ 1.5 推进时增量更新**。每完成 1 个 task,加 1 行证据。
- **最终 verify.md**(7.2 task)在所有 12 个新 task 完成后写,包含完整 18 个 requirement 的 requirement-by-requirement 证据。
- **本 change apply 阶段起点**:2026-06-14(task 1.1 完成时间)。完成 1/12,剩 11 个。

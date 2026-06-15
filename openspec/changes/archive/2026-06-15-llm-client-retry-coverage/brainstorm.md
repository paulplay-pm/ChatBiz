<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/llm-client-retry-coverage`.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
Skill 的自然產出通常是 decision log 格式（背景 → 決議鏈 Q1-Qn → 設計取捨），
但依對話內容可能有不同組織方式。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: llm-client-retry-coverage

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 紧接 `coverage-improvement` + `gateway-scanner-coverage-matrix`
2 个 change push 后（commit 1818495 latest），立即 follow
`coverage-improvement/retrospective.md §4.2` + §4.4。

---

## 背景

`coverage-improvement/retrospective.md §4.2` 提议的下一条 change：

> | `retry_with_idempotency` wrapper body (client.py:240-304) |
> | name: `llm-client-retry-coverage` |
> | scope: 补 `retry_with_idempotency` 的 3-attempt/5s 预算 /
> HA_FAILOVER 503 重试 / `last_exc` raise / `last_resp` return
> 4 个分支的 unit test |

**关键现状调研**（apply 阶段必须拿到的 evidence，已在 chat 跑过）：

跑 `pytest tests/unit/test_coverage_gaps_v1_followup.py
tests/unit/test_retry.py --cov=app.llm.client --cov-report=term-missing`:

- `app/llm/client.py`：108 stmts，**24 miss，78%**
- Missing：74-80 / 104-120 / 214-215 / 304 / 334
- 23 个 test 已在 `tests/unit/test_retry.py` + 22 个新 test 在
  `tests/unit/test_coverage_gaps_v1_followup.py` = 45 个 test PASS
- Line 121 `raise last_exc or RuntimeError(...)` in `retry_with_redis`
  + line 304 `raise RuntimeError(...)` in `retry_with_idempotency`
  都已经 source 标了 `# pragma: no cover`

**Missing 详情**：

| Lines | What | 触发条件 |
|---|---|---|
| 74-80 | `get_client()` lazy init | 第一次调 `get_client()` 时 `_client is None` |
| 104-120 | `retry_with_redis` body (2-iter loop) | 5xx retry + connection-interrupted exception |
| 214-215 | `_is_ha_failover` `resp.json()` raises | HA 503 + body 不可 JSON parse |
| 304 | `raise RuntimeError(...unreachable...)` | Defensive, 已 `# pragma: no cover` |
| 334 | `reset_client_for_tests()` body | 调它时 |

**真 reachable missing = 27 行**(减 304 的 `# pragma: no cover`)。

## 决议链

### Q1: change name 用什么？

- 选项 A：`llm-client-retry-coverage`（retrospective §4.2 原话）
- 选项 B：`client-py-100pct-line-cov`（更泛）
- 选项 C：`retry-decorator-coverage`（更窄，只 retry decorator）

**决议**：**A**。理由：
- 与 `coverage-improvement/retrospective.md §4.2` 引用链 1:1
- "retry-coverage" 暗示 retry decorator 是重点，但**实际** missing 包含
  `get_client` lazy init + `_is_ha_failover` 错误路径，scope 不止 retry
- 不缩到 `client-py-100pct-line-cov`：太泛，未来其他 client.py 改动
  （如新 endpoint）会被错误归到这里

**显式拒绝**：
- **B**——`client.py` 是 `llm` service 的核心，未来其他 100% 改动会有
  自己的 change name
- **C**——`retry-decorator-coverage` 排除 `get_client` 等 missing，scope
  缩太窄

### Q2: scope 多宽？

- 选项 A：只补 ~6-8 个 test 让 client.py 24 missing 行 100% covered
- 选项 B：同上 + 把 `__main__.py` / `scanner.py` 等其他文件也补 100%
- 选项 C：同上 + 加 CI workflow 跑 cov

**决议**：**A**。理由：
- retrospective §4.2 明确说"补 4 个分支的 unit test"，是 narrow scope
- 选项 B 把 scope 扩大到整个 audit-and-isolation 100% — 跟
  `coverage-improvement` 重叠（`coverage-improvement` 已 close
  audit-and-isolation 3 模块 100%）
- 选项 C 是 `ci-coverage-all-services` 范围

**显式拒绝**：
- **B**——`coverage-improvement` 已 close audit-and-isolation 3 模块
  100%（archive commit 7fe8e91）
- **C**——`ci-coverage-all-services` change 范围

### Q3: 怎么测 `get_client()` lazy init (line 74-80)?

`get_client()` 用 module-level `_client` 缓存 + 第一次 `if _client is None`
init `httpx.AsyncClient(timeout=..., limits=...)`。要测这个分支需:
- 跑 test 前 `reset_client_for_tests()` 删缓存
- mock `get_settings()` 返回 `upstream_timeout_ms=...`
- 调 `get_client()`,断言 `httpx.AsyncClient` 被 init

**决议**：**测**。理由：
- 6 行 missing 是真 reachable
- 现有 `test_retry.py` 已有 `reset_client_for_tests()` 调用 pattern
- 跟 `coverage-improvement` 同 pattern(`env var setdefault` 在 file 头)

### Q4: `retry_with_redis` body (104-120) 怎么测?

`retry_with_redis` 是 `call_upstream` 装饰器(2 iter loop),missing 17 行
覆盖 3 个分支:
- 5xx retry: `resp.status_code >= 500 and attempt == 0` → sleep 0.2s → continue
- Connection interrupt exception: `httpx.TimeoutException / RemoteProtocolError` → sleep → continue
- Last iteration: 直接 return resp 或 raise last_exc

**决议**：**3 个 test** 各走一个分支。理由：
- 跟 spec 4 个分支的"3-attempt" 不同(那指 `retry_with_idempotency` 的
  3-iter,本 change 测的是 `retry_with_redis` 的 2-iter)
- 17 missing 拆 3 个 test 干净

### Q5: `_is_ha_failover` 错误路径 (214-215) 怎么测?

`_is_ha_failover(resp)` 调 `resp.json()`,如果 JSON parse raises → return
False(不算 HA failover)。missing 2 行 = `except Exception: return False` 分支。

**决议**：**1 个 test**。理由：
- 1 mock `httpx.Response`,`resp.json.side_effect = ValueError(...)`
- 调 `_is_ha_failover(resp)`,assert False

### Q6: 改 `__main__.py:99` / `scanner.py:213` 这种 `# pragma: no cover`?

**不需要**。line 304 (client.py) 已经在 source 标了 `# pragma: no cover`
(行 121 同样)。本 change 0 行 source 改动。

**决议**：**A**。理由：line 304 已标,line 121 已标,本 change 不需要新标。
如果跑 cov 后发现**新** unreachable branch,再 surface 给用户决策。

### Q7: 走完整 openspec 8 artifact 流程吗?

**决议**：**是**。理由：跟 `coverage-improvement` + `gateway-scanner-coverage-matrix`
同 pattern,6 artifact 模板已建立。

## 设计取捨

### 单一方案：openspec 完整流程

跟前 2 条 coverage change 同 pattern。apply 阶段会:
1. 跑 cov 拿 4 个 reachable missing 区域(已 chat 跑过,line 74-80/104-120/214-215/334)
2. 补 ~6-8 个 test
3. 0 行 source 改动(line 304 已 `# pragma: no cover`)
4. 单 commit + push + archive

### 拒绝的方案汇总

| 方案 | 拒绝理由 |
|---|---|
| Ad-hoc git commit | 违反 CLAUDE.md openspec 流程 |
| 走完整 brainstorming 本地 design doc | 前 2 个 change 显式跳过,openspec design.md 替代 |
| Scope 扩大全 audit-and-isolation 100% | `coverage-improvement` 已关 |
| Scope 缩到 retry decorator only | 排除 `get_client` 等 missing,scope 太窄 |
| 加 CI workflow | `ci-coverage-all-services` change 范围 |

## Open Questions（本轮未决）

**无**。所有决策在 chat 一次性问完,无未决项。

## Brainstorm facilitator self-check

- [x] 探索了 project context（跑了 pytest --cov,看了 4 个 missing 区域
      具体行号,确认了 line 304/121 已是 `# pragma: no cover`）
- [x] 没问视觉问题（纯测试 followup）
- [x] 一次问完 1 个多选题（scope），未多轮往返
- [x] 给出 2-3 approaches + 推荐（Q1 / Q2），其他是 binary decision
- [x] 列出显式拒绝方案 + 理由
- [x] Open Questions 段明确写"无"
- [x] 决议触及 eng-review 锁定决策？**未触及**——纯 test followup
- [x] 决议触及 3 个具名用户 workflow？**未触及**——`client.py` retry
      decorator 跟 paul/leo/anny workflow 都不直接相关

## 移交到 design.md 的内容

design.md 应从本檔萃取并重组为：
- **Context**: 见上文"背景"段
- **Goals**:
  - G1: `app/llm/client.py` 从 78% → 100% line coverage
  - G2: 0 行 source 改动（line 304/121 已是 `# pragma: no cover`）
  - G3: 既有 23 test + 22 新 test 不被破坏
- **Decisions**: 见上文"决议链" Q1-Q7
- **Risks**:
  - R1: `retry_with_redis` body 测需要 mock `httpx.AsyncClient` +
    `asyncio.sleep`,可借鉴 `test_retry.py` 已有 pattern
  - R2: `get_client()` lazy init 测需要先 `reset_client_for_tests()`
- **Migration**: 不适用

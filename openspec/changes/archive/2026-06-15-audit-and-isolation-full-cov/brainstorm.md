<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/audit-and-isolation-full-cov`.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: audit-and-isolation-full-cov

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 紧接 `ci-coverage-sso` (5389f41) push 后。
`llm-client-retry-coverage/retrospective §4.4` 提议的下一条 change,
摸 audit-and-isolation service 整体 cov 起点 + 补 4 module partial
达 100%。

---

## 背景

### 现状摸底（apply 阶段 chat 跑过）

`cd services/audit-and-isolation && pytest tests/ --cov=app --cov-report=term-missing`:
- 41 module,**34 个 100%** + 4 module partial:

| Module | Stmts | Miss | Cover |
|---|---|---|---|
| `app/api/audit_archive.py` | 85 | 4 | 95% |
| `app/api/chat.py` | 142 | 6 | 96% |
| `app/api/traces.py` | 53 | 3 | 94% |
| `app/perf/contracts.py` | 54 | 3 | 94% |

**总 missing = 16 行 / 4 module**。比 `ci-coverage-sso` 的 65 missing 小 4x。

### Missing lines 详情

| Module | Lines | What |
|---|---|---|
| `audit_archive.py` | 95 | raise ValueError on malformed date |
| `audit_archive.py` | 132-133 | JSON decode error log |
| `audit_archive.py` | 158 | `body.read()` for `body` is uploaded file (UploadFile) |
| `chat.py` | 228-229 | observe_request 200 + return echo_response (echo path) |
| `chat.py` | 258-259 | observe_request + return Response (no-bypass path) |
| `chat.py` | 320-323 | RequestBatcher.submit + await upstream_future (bypass-is-disabled path) |
| `traces.py` | 91-94 | JSON decode error log + return None (corrupted cache) |
| `perf/contracts.py` | 216-218 | NoopRequestBatcher.submit returns _never event await |

### Trigger retrospective §4.4

> | name: `audit-and-isolation-full-cov` |
> | scope: 摸 41 module 起点 + 补 test |
> | estimated effort: 估 1-2 hours |

**实际估**: 4-5 test,~20-30 min(16 missing lines 跨 4 module)

## 决议链

### Q1: change name 用什么？

- 选项 A: `audit-and-isolation-full-cov`(retrospective §4.4 原话)
- 选项 B: `audit-isolation-4-module-coverage`(更具体)
- 选项 C: `audit-isolation-cov-followup`(泛)

**决议**：**A**。理由：
- 跟 `llm-client-retry-coverage/retrospective §4.4` 引用链 1:1
- "full-cov" 暗示 service 整体 100% 目标

### Q2: scope = 补 4 module partial 达 100%?

**决议**：**是**。理由：
- 4 module 16 missing lines, 估 4-5 test
- 跟 6 个前 coverage change 同 pattern
- accept fail-under 100% 在 apply 阶段会 trigger 通过

### Q3: 0 行 prod code 改动?

**决议**：**是**。理由：纯 test followup。

### Q4: 走完整 openspec 8 artifact?

**决议**：**是**。理由：6 个前 change 同 pattern。

## 设计取捨

### 单一方案：openspec 完整 6 artifact + apply

### 拒绝的方案

| 方案 | 拒绝理由 |
|---|---|
| Ad-hoc git commit | 违反 CLAUDE.md openspec 流程 |
| 跳 6 artifact | schema 强制 |

## Open Questions

**无**。

## Brainstorm facilitator self-check

- [x] 探索了 project context(跑了 pytest --cov, 摸 4 module missing)
- [x] 没问视觉问题
- [x] 1 个多选题(scope 拆分)
- [x] 列出 2-3 approaches + 推荐
- [x] 列出显式拒绝方案
- [x] Open Questions 段明确写"无"
- [x] 决议触及 eng-review 锁定决策？**未触及**——纯 test followup
- [x] 决议触及 3 个具名用户 workflow？**未触及**——纯 test followup

## 移交到 design.md

- Context: 见上文"背景"段
- Goals: G1 4 module 100% / G2 0 行 prod 改
- Decisions: 见 Q1-Q4
- Risks: R1 apply 阶段 test mock 复杂度 / R2 spec claim 漂移
- Migration: 不适用

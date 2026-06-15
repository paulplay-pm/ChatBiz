## Context

`llm-client-retry-coverage/retrospective §4.4` 提议的下一条 change。

**当前状态**(apply 阶段 chat 跑过):
- 41 module,**34 个 100%** + 4 module partial(16 missing lines 跨 4 module)
- 既有 384 PASS,4 module partial

**约束**:
- 0 行 prod code 改动
- 0 新 PyPI 依赖
- 不动 12 个 eng-review 决策

## Goals / Non-Goals

**Goals**:
- **G1**: 4 module(`audit_archive.py` / `chat.py` / `traces.py` / `perf/contracts.py`)达 100%
- **G2**: 0 行 prod code 改动
- **G3**: 既有 384 PASS 不被破坏

**Non-Goals**:
- **NG1**: 不改 `app/` 下 prod code
- **NG2**: 不加 CI workflow
- **NG3**: 不重写 4 module 现有 34 个 test

## Decisions

### D1: change name = `audit-and-isolation-full-cov`
跟 retrospective §4.4 引用链一致。

### D2: scope = 4 module 100%
跟 6 个前 coverage change 同 pattern。

### D3: 0 行 prod code 改动
纯 test followup。

### D4: 走完整 openspec 8 artifact

## Risks / Trade-offs

- **[Risk] R1**: apply 阶段 mock 复杂(`RequestBatcher.submit` 是 async, `UploadFile.read()` 需 mock)
  → Mitigation: 1 test 1 pytest verify cycle

- **[Trade-off] T1**: 4 module partial 接受 "low-hanging module" 表述,不接受 100% 是 spec drift
  → 接受理由: 16 missing 是摸底后看到的事实,比 sso 65 missing 易管理

## Migration Plan

N/A。

**部署顺序**:
1. 跑 cov 拿 4 module missing lines (apply Task 1)
2. 写 4-5 个新 test
3. 跑 cov verify 100%
4. prod diff check
5. git add + commit
6. openspec archive

**验收条件**:
- 4 module 100% line cov
- 0 行 `app/` 改动
- 既有 384 PASS 保持

## Open Questions

**无**。

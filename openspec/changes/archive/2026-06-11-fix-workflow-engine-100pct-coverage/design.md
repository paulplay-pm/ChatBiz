## Context

CLAUDE.md 与 `openspec/config.yaml` 锁定 workflow-engine 100% 单元测试覆盖率。当前 focused smoke 通过但 coverage 57%。`fix-canvas-real-tests` verify.md §8 显式记录此为 follow-up。

## Goals / Non-Goals

**Goals:**
- 补足 workflow-engine 全部模块的单元测试,实现 100% 覆盖率。
- 不改产品代码,不改 coverage 阈值。
- 真实运行 `python -m pytest tests/ --cov-fail-under=100` 必须通过。

**Non-Goals:**
- 不引入新测试框架。
- 不动产品 API 行为。

## Decisions

### D1: 测试组织
- **选择**: `services/workflow-engine/tests/unit/test_*.py` 新增子目录,集中放纯函数 / API / 节点单元测试。e2e 和 security 保持不动。
- **理由**: 区别 happy-path focused smoke 与 exhaustive coverage。

### D2: Mock 策略
- **选择**: httpx 客户端用 respx;LangGraph 编译用 monkeypatch;cron 任务用 aiosqlite + freezegun。
- **理由**: 现有依赖栈已支持,无新引入。

### D3: Phase 顺序
按 ROI 排序,从纯函数到 IO-heavy:
1. `errors/`, `clients/`, `executor/retry.py`, `graph/conditional.py` (纯函数 + httpx)
2. `cron/`, `executor/runner.py`, `executor/sse.py` (异步 + time/IO)
3. `graph/compiler.py`, `nodes/*` (LangGraph 集成)

## Risks / Trade-offs

- **Risk**: LangGraph 0.2 内部 API 复杂,可能难以 mock
  → **Mitigation**: Phase 3 失败时回退为排除 `compiler.py` 的若干行,记录为新增 follow-up
- **Risk**: 全部覆盖 = 大量测试代码
  → **Mitigation**: 不追求 README 完美,只追求测试触发实际代码路径

## Migration Plan

1. 写 `tests/unit/test_*.py` 多个文件
2. 跑 `python -m pytest tests/ --cov-fail-under=100`
3. 修到 100%
4. commit
5. archive + merge

## Open Questions

无
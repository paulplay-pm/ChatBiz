# brainstorm: fix-workflow-engine-100pct-coverage

## 背景

`fix-canvas-real-tests` 中已确认: workflow-engine 真实 focused smoke 13/13 通过,但默认 `--cov-fail-under=100` 仍失败,当前 57% coverage。CLAUDE.md 锁定 100% 单元覆盖率,此 follow-up 必须补到 100% 才能启用默认 coverage gate。

主要缺口(按文件):
- `app/executor/retry.py` 0% (17 行纯函数)
- `app/graph/conditional.py` 0% (16 行纯函数)
- `app/graph/compiler.py` 20% (66 行,核心 LangGraph 编译)
- `app/executor/runner.py` 33% (55 行,异步 background)
- `app/executor/sse.py` 31% (36 行,SSE 消费者)
- `app/cron/approval_timeout.py` 41% (39 行,24h 超时)
- `app/cron/cleanup.py` 67%
- `app/api/*.py` 整体 25-74%(workflows/validate/run/health/nodes/approvals/runs)
- `app/clients/*.py` 37-86%(httpx 客户端 + respx mock)
- `app/nodes/*.py` 14 个节点 43-100%(实际执行逻辑)
- `app/errors/middleware.py` 79%

## 决策

### Q1: 范围与优先
- **纯函数 / 易测** (高 ROI): `errors/`, `clients/`, `graph/conditional.py`, `executor/retry.py`, `nodes/<simple>` 优先
- **需要 mock 的**: `clients/*` 用 respx 已有模式;`cron/*` 用 aiosqlite + 时间冻结(freezegun)
- **需要重写或加依赖的**: `graph/compiler.py` 用 monkeypatch mock `langgraph`;`executor/runner.py` 用 `asyncio.create_task` 跟踪

### Q2: 修复方式
**不降低 coverage 阈值,直接补到 100%**。理由:CLAUDE.md 锁定规则,且这是显式 follow-up,不是新需求。

### Q3: 进度策略
- **Phase 1** (高 ROI): `executor/retry.py`, `graph/conditional.py`, `errors/`, `clients/` 全部 → 估 +30 行代码 + 10 测试 → ~70% coverage
- **Phase 2** (中 ROI): `executor/runner.py` + `sse.py` + `cron/*` → 估 5 测试 → ~85%
- **Phase 3** (深): `graph/compiler.py` + `nodes/*` 全部执行路径 → 估 15 测试 → 100%

如时间紧,允许 Phase 3 部分延迟。但本 change 目标 = 100%。

## Non-goals
- 不改产品逻辑
- 不改 spec 范围(本 change 已被 archive 100% coverage 要求)
- 不引入新测试框架(只用 pytest + respx + freezegun + aiosqlite 现有栈)

## Open Questions
无
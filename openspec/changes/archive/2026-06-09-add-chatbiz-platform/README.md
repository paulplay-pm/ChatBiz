# add-chatbiz-platform

> **Archived**: 2026-06-09
> **Status**: DRAFT specs archived to `openspec/specs/<cap>/` (12 capabilities, 72 requirements)
> **Schema**: superpowers-bridge

## 这是什么

ChatBiz 企业级 AI Agent 平台 —— 基于 `docs/architecture.md` + `docs/prd.md` + `docs/prototype.html` 生成的完整 OpenSpec 规范,覆盖 9 核心 capability + 3 横切 capability。

本 change **不实施任何代码**。它是规范定义 change,产物 = 12 个 cap 的 OpenSpec spec,作为后续每个 cap 实施 change 的契约基础。

## tasks.md 状态说明

`tasks.md` 里有 73 个 task,但 **9 个是本 change 的工作,64 个是未来 9-12 月的实施路线图**,全部预期未勾选。

| Task group | 数量 | 状态 | 含义 |
|---|---|---|---|
| §1 本 change 自身验收 | 9 | ✅ 全部勾选 | 12 spec 已写、validate 通过、archive 完成 |
| §2 全局前置 | 10 | 未勾选 | 月 1 启动条件(sponsor / FTE / 基础设施 / 凭证 / 网关 / Node Contract / 状态层 / 错误边界 / 测试金字塔 / critical path) |
| §3 MVP (月 2-3) | 13 | 未勾选 | 9 个 cap 的 MVP 实现 + audit-and-isolation + MVP 验收 |
| §4 V1.0 (月 5-6) | 10 | 未勾选 | V1.0 增量(其余 7 节点 / Rerank / fallback / IM 通道 / SSO / 告警 / API) |
| §5 V1.5 (月 8-9) | 6 | 未勾选 | 企业级集成 |
| §6 V2.0 (月 11-12) | 6 | 未勾选 | 生态 + 多租户 + 性能 + i18n |
| §7 横切持续 | 5 | 未勾选 | 编码规范 + verification + archive 流程 |
| §8 critical path 回归 | 4 | 未勾选 | 4 critical path 测试持续维护 |
| §9 sponsor 风控 | 4 | 未勾选 | 9-12 月 sponsor 沟通 / 风险复盘 |
| §10 实施约束 | 6 | 未勾选 | HA / Node Contract / 双层状态等强制项 |

§2-10 **不是本 change 的未完成项**,是未来每个 cap 实施 change 的 coarse-grained 路线图。每个 cap 实施时:

1. `openspec new change implement-<cap>` (新 change)
2. 引用本 change 的 `openspec/specs/<cap>/spec.md` 作为契约
3. 从对应的 §3-6 task 里挑属于本 cap 的细化为 tasks.md §1-N
4. 实施 + 测试 + archive

**本 change 走 archive 的原因**:`openspec archive` 把 incomplete tasks 当作 warning (不是 error),`-y` 跳过警告后强制 archive。本 change 的真正目的是把 12 个 cap spec 落到 `openspec/specs/`,这个目标已完成。

## eng-review 集成

12 个 eng-review 锁定决策以 `[ENG-#N]` 引用形式写进每个 cap spec 的顶部。完整决策描述在 `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` 的 `## GSTACK REVIEW REPORT`。

## 后续 cap 实施顺序(粗粒度)

按依赖图,月1 启动 3 个并行 Lane:

```
月1:  Lane A credential-management  (1 后端)
      Lane B audit-and-isolation  (1 后端网关)
      Lane C system-management   (1 后端 + 1 全栈)

月2:  Lane D knowledge-base  (depends A+B)
      Lane E api-gateway      (depends C)
      Lane F channel-management (depends A+C)
      Lane G monitoring        (独立,可任意)

月3:  Lane H model-management  (depends A+B+D)
      Lane I plugin-market    (depends A+B+G)

月4:  Lane J agent-runtime  (depends H+I)
      Lane K workflow-engine (depends J+D+I)

月5+: Lane L skill-management (depends J+I)
```

workflow-engine 不是先做,是最后做 —— 它是"末端粘合层",等所有依赖 cap 都做完再做反而比从头做更快。
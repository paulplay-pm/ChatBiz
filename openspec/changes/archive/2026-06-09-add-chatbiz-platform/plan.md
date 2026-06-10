# ChatBiz 平台 OpenSpec 规范 Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 12 个 capability 的 OpenSpec 规范落地为 apply-ready;后续每个 cap 实施时开新 change(走 openspec-apply)。

**Architecture:** 9 核心 + 3 横切 capability spec,引用 eng-review 12 个 locked-in 决策,以 `[ENG-#N]` 简写。本 change 纯规范定义,不实施任何代码。

**Tech Stack:** Python 3.9+ / OpenSpec CLI / Markdown / Git worktree / openspec-propose workflow.

---

## Task 1: 本 change 自身产物验收(已大部分完成,只需最后 verify + archive)

**Files:** (本 change 目录:`/Users/paulwang/work/ChatBiz/openspec/changes/add-chatbiz-platform/`)

- [ ] **Step 1:** 跑 schema validate
  ```bash
  openspec schema validate 2>&1
  ```
  Expected: `✓ superpowers-bridge` 通过

- [ ] **Step 2:** 跑 status 看 artifact 完成度
  ```bash
  openspec status --change "add-chatbiz-platform" --json | jq '.artifacts[] | {id, status}'
  ```
  Expected: brainstorm / proposal / design / specs / tasks / plan 全部 `done`(7/8,verify+retrospective 是 post-apply 不需要)

- [ ] **Step 3:** 检查每个 spec 文件的硬约束
  ```bash
  for f in /Users/paulwang/work/ChatBiz/openspec/changes/add-chatbiz-platform/specs/*/spec.md; do
    echo "=== $f ==="
    # 必须含 SHALL 或 MUST
    grep -qE 'SHALL|MUST' "$f" || echo "FAIL: missing SHALL/MUST"
    # 必须至少 1 个 #### Scenario
    grep -qE '#### Scenario:' "$f" || echo "FAIL: missing Scenario"
    # 必须有 eng-review-refs
    grep -qE 'eng-review refs' "$f" || echo "FAIL: missing eng-review refs"
  done
  ```
  Expected: 12 个 spec 全部无 FAIL 输出

- [ ] **Step 4:** 确认 openspec list 看 change 状态
  ```bash
  openspec list
  ```
  Expected: `add-chatbiz-platform` 列出

- [ ] **Step 5:** Archive change(本 change 不实施,直接 archive)
  ```bash
  openspec archive add-chatbiz-platform
  ```
  Expected: specs 合并入 `openspec/specs/<cap>/`,change 移到 `openspec/changes/archive/`

- [ ] **Step 6:** Verify archive 结果
  ```bash
  ls /Users/paulwang/work/ChatBiz/openspec/specs/ 2>&1 | head -20
  ls /Users/paulwang/work/ChatBiz/openspec/changes/archive/ 2>&1 | head -5
  ```
  Expected: 12 个 cap spec 在 `openspec/specs/`,`add-chatbiz-platform` 在 archive/

- [ ] **Step 7:** Commit(this branch)
  ```bash
  git add openspec/
  git commit -m "feat(spec): add ChatBiz platform OpenSpec规范 (12 capabilities, 9 core + 3 cross-cutting)"
  ```

---

## Task 2: 后续 cap 实施的全局前置(每个 cap 实施 change 的第一阶段)

**Files:** (每个 cap 实施 change 在自己的 worktree,不在本 change 范围)

- [ ] **Step 1:** 验证 sponsor 承诺(由工程经理完成,非技术任务)
  - 检查 OKR 系统是否有 9-12 月 ChatBiz 时间承诺
  - 缺失则阻塞月 1,surface 给用户

- [ ] **Step 2:** 锁定 5-7 FTE
  - 1 后端网关(services/gateway/)
  - 1 后端 LangGraph(services/runtime/)
  - 2 前端画布(web/canvas/)
  - 1 全栈集成(services/integration/)
  - 0.5 运维(infrastructure/)
  - 关键稀缺:1 LangGraph 后端 + 2 React Flow 资深前端
  - month 1 必须到位

- [ ] **Step 3:** 基础设施起步 (单 VM + docker-compose)
  ```bash
  # docker-compose.yml 在仓库根 /infrastructure/
  docker compose up -d postgres redis minio
  ```
  Expected: 3 services 启动;不引入 K8s / Milvus / Kafka

---

## Task 3: 数据隔离网关(audit-and-isolation 第一个 cap 实施) — 跨所有 cap 依赖

**Files:** (在 cap-specific change 里,不在本 change 范围)
- `services/gateway/server.py`(FastAPI)
- `services/gateway/trace.py`(trace-id 关联)
- `services/gateway/pii.py`(PII 脱敏)
- `services/gateway/cache.py` `ratelimit.py` `batch.py`(性能三件套)
- `infrastructure/k8s/gateway-deployment.yaml`(HA 2 实例)

实施要点:参考 eng-review [ENG-Arch #1] + [ENG-Perf #1] + [ENG-Quality #3]。

---

## Task 4: Node Contract 实施(workflow-engine cap 前置) — 跨 cap 共享

**Files:**
- `contracts/nodes/base.py`(TypedDict 定义)
- `contracts/nodes/gen.py`(代码生成器)
- `contracts/nodes/tests/`

实施要点:12 节点类型共享 1 份 schema,生成 4 份代码(画布 UI / StateGraph / schema / validator)。参考 [ENG-Arch #2] + [ENG-Quality #1]。

---

## Task 5-N: 每个 cap 实施(走 openspec-apply + subagent-driven-development)

每个 cap 一个新 change,follow 这个 plan template 的简化版:
1. 跑 `openspec new change <cap>-implementation --schema superpowers-bridge`
2. 写 tasks.md(≤ 2h 粒度,配对 verify task)
3. 写 plan.md(micro-steps + commit 点)
4. `openspec apply <cap>-implementation`(创建 worktree)
5. 实施(用 subagent-driven-development 派 subagents,每 task 派一个)
6. 关键节点(节点完成 / 测试通过 / review 通过)checkpoint commit
7. `openspec verify <cap>-implementation` + 跑 4 critical path
8. `openspec archive <cap>-implementation`
9. Merge to main(走 PR 流程,需 1 reviewer)

按 PRD §8.1 里程碑组织:
- 月 2-3 (MVP):workflow-engine / agent-runtime / knowledge-base / plugin-market / model-management / system-management / channel-management (仅 Web) / credential-management / audit-and-isolation = **9 个 cap** (skill-management 和 api-gateway 在 MVP 阶段仅 spec 落地)
- 月 5-6 (V1.0): 12 个 cap 全部 + 4 critical path
- 月 8-9 (V1.5):企业集成
- 月 11-12 (V2.0):生态 + 性能 + 多租户

---

## Self-review (per writing-plans skill)

**Spec coverage check:** 每个 cap spec 至少 1 个 Scenario ✓ (Task 1 Step 3 verify)
**Placeholder scan:** 没有 TBD / TODO / "implement later" ✓
**Type consistency:** 所有 spec 用相同模板 ✓ (MUST / SHALL / #### Scenario)
**File path consistency:** 使用仓库实际路径 ✓ (services/gateway/、web/canvas/、contracts/nodes/)

## References

- `docs/architecture.md` §4 — 技术架构
- `docs/prd.md` §8 — 里程碑
- `~/.gstack/projects/paulplay-pm-ChatBiz/paulwang-main-design-20260609-230548.md` — eng-review 12 决策
- 12 个 cap spec 在本 change `specs/<cap>/spec.md`

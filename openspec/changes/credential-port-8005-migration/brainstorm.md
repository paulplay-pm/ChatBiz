# credential-port-8005-migration — Brainstorm

> Raw capture. `superpowers:brainstorming` skill 不可用,按 fallback 手写 decision log。

---

## 背景与现状

`infrastructure/docker-compose.yml` 把 `credential` 服务的 host port 映射为 `8000:8000`。本机 Trae IDE 占着 `0.0.0.0:8000` (PID 7703, IPv6),导致 `docker compose -p chatbiz up` 必 fail 在 credential 容器启动阶段。

`web-integration-test-suite` 与 `fix-production-compose` 两个 change 都记录此为 "BLOCKED" 验证项。要让 7-service 端到端在干净 dev 机外的本机也能跑通,必须换 host port。

**关键约束**:
- CLAUDE.md 端口表: 8000 "已分配" 给 credential; 8005+ 标 "未来 可用,新 service 从 8005 开始往后分配"
- 选 8005 = 第一个 "未来" 端口,符合 CLAUDE.md "新 service 从 8005 开始往后分配" 约定
- Container-internal port (8000) **不能动**: 已有 service 消费 `credential:8000` DNS (audit-and-isolation + workflow-engine + credential healthcheck Dockerfile)
- 改动范围: 仅 host port mapping + 2 处 user-facing 文档/CLI

---

## 候选方案

### 方案 A: 8000 → 8005,container-internal 不动(推荐)

```text
infrastructure/docker-compose.yml
  ports:
    - "8005:8000"   # was "8000:8000"

infrastructure/README.md
  curl http://localhost:8005/healthz  # was localhost:8000

services/credential/locust/locustfile.py
  --host http://localhost:8005  # was localhost:8000

CLAUDE.md 端口表
  8005  credential  已分配  chatbiz-credential (migrated from 8000)
  8000  (旧) 释放 — 留作历史记录或注销
```

**优点**:
- Container-internal 不动 → audit-and-isolation / workflow-engine / 既有 Docker healthcheck 零改动
- 8005 在 CLAUDE.md "未来" 范围,合规
- 改 3 文件 + CLAUDE.md
- 端到端 7-service up 在本机能跑通 (Trae 只占 8000,8005/8080/8001/8004/5432/6379 全 free)

**缺点**:
- CLAUDE.md 端口表 8000 行的状态需明确 (释放/历史/留空)
- 部分 user 文档 / 脚本需同步更新
- 一旦 merge, 任何旧 CI/本地 `localhost:8000` 调用失效

### 方案 B: 完全删 host port mapping(类似 test stack 模式)

```text
infrastructure/docker-compose.yml
  credential:
    # no ports: mapping (容器仅暴露给 compose-internal DNS)
```

**拒绝理由**:
- 用户无法在 host 上 `curl http://localhost:XXXX/healthz` 验 credential (只能通过 nginx proxy)
- 失去直接调试 capability (Locust 性能测试、debug shell)
- dev compose 用 `extends` 继承 production,改动会污染 dev (虽然 dev override 自己的 ports)
- 与 "port table" 既定约定冲突 (CLAUDE.md 显式给 credential 分配端口)

### 方案 C: 改 8000 → 8004 (用 mcp 的端口)

**拒绝理由**:
- 8004 已分配给 mcp;CLAUDE.md 显式标"已分配 chatbiz-mcp"
- 端口冲突检测规则 "命中保留位要先跟 change 沟通挪位" — 不可用

---

## Rejected Alternatives

| 方案 | 拒绝理由 |
|---|---|
| B. 不暴露 host port | 失去直接调试 + 与 port table 约定冲突 |
| C. 用 8001 / 8004 等已分配 | CLAUDE.md 冲突检测规则禁止 |
| D. 用 8080 / 5173 等其他 service 端口 | 同样冲突 |
| E. 完全换 credential 实现(不用 FastAPI) | scope creep;与本 change 无关 |

---

## 关键决策

### D1: 选 8005 (CLAUDE.md "未来" 范围第一个)
最简、合规、不动 container-internal。

### D2: Container-internal port 8000 **保持**
CREDENTIAL_SERVICE_URL=http://credential:8000 既是 compose DNS + 容器内端口,其他 service 不需要改任何 env。

### D3: 只改 3 文件 + CLAUDE.md 端口表
- `infrastructure/docker-compose.yml`: `8000:8000` → `8005:8000`
- `infrastructure/README.md`: localhost:8000 → localhost:8005 (1 行)
- `services/credential/locust/locustfile.py`: --host localhost:8000 → 8005 (1 行)
- `CLAUDE.md` 端口表: 8000 行标"已迁移到 8005",加 8005 行

### D4: 端口表 8000 行不删 (保留审计追踪)
标记"已迁移到 8005" + 注释 "见 change credential-port-8005-migration (2026-06-13)";新 reader 看注释知道历史;但**不**在表里重新分配 8000 (避免未来 service 误用)。

### D5: openspec/config.yaml §apply.rules
- "MUST: 端口从 CLAUDE.md 端口分配表选用" — **满足** (8005 标记为"未来",CLAUDE.md "新 service 从 8005 开始往后分配" 明文允许)

---

## 风险与 Open Questions

### 风险

1. **本机 / 远端 CI 的 8005 被占** — lsof 本机 8005 free;但 CI 跑同一份 compose 需确认 CI 8005 也 free。**Mitigation**: verify 步骤显式 `lsof -i :8005` 检查。
2. **8000 上若已有 dev 工具监听** — Trae 占 8000 仍占;但本机 8005 释放后 credential 可正常 bind。**Mitigation**: 无需。
3. **既有 Locust 性能测试** — `services/credential/locust/locustfile.py` 显式 --host;改 1 行即可。

### Open Questions

1. **OQ1**: 改完后 `docker compose -p chatbiz up --wait` 在本机能否跑通 7-service? **答**: 应能 (port 8005 free + 之前 fix 已修 3 个 compose bug)。verify 阶段直接跑。
2. **OQ2**: 改 CLAUDE.md 端口表时,8000 行的状态填什么? **答**: 标"已迁移到 8005" + 注释,见 D4。
3. **OQ3**: 旧 `docker compose -p chatbiz-test` 用的 8000:8000 是否也要改? **答**: test compose 当前 **未** 暴露 host 8000 (worktree-web-integration-test-suite 已删除 host port mapping),所以 test stack 不受影响。

---

## 与 eng-review 锁定决策的映射

| eng-review finding | 本 change 如何覆盖/对齐 |
|---|---|
| **Test #1** 3 层测试金字塔 | 解阻塞 7-service 端到端 → 后续 CI change 可直接跑 |
| **Test #2** 4 critical path | 解阻塞 ① paul 完整链路 (前两个 change 已落代码) |
| (其他 12 finding) | 不涉及 |

---

## 下一步

1. 写 `proposal.md`: scope = 4 文件改 + 1 端口表行
2. 写 `design.md`: D1-D5 + 验证矩阵
3. 写 `specs/credential-port-migration/spec.md`: 4 个 Requirement
4. 写 `tasks.md`: 6-8 个 task
5. 写 `plan.md`、`verify.md`、`retrospective.md`
6. apply 阶段: 改 4 文件 + 在本机跑 `docker compose -p chatbiz up --wait` 7-service healthy 验证

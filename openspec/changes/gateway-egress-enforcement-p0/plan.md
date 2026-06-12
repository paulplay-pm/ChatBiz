# Gateway Egress Enforcement 实施计划(补差模式)

> **For agentic workers:** Use superpowers:subagent-driven-development
> to implement this plan task-by-task. 仓库 `services/audit-and-isolation/`
> 已实现本 spec 80% 功能(2335 行 Python,eng-review Arch #1 引用)。
> gap-analysis.md 标 18 task 已 done,**本 plan 只列 20 个补差 task**(其中 12 个新实现 + 7 个 [EXISTING] 引用 + 1 个 verify)。

**Goal:** 在 `services/audit-and-isolation/` 已有实现之上,补 HA 拓扑 + 编译期静态扫描 + 定时归档 + trace 跨实例查询 + perf contracts + `/metrics` 端点 + `docs/architecture.md` §4.3.Y PII 规则集段,完成数据隔离网关 P0 周边。MVP 2-3 月内让 paul 财务月报工作流跑通。

**Architecture:** audit-and-isolation 双实例 active-active + NGINX stream L4 LB + K8s preStop 排空(terminationGracePeriodSeconds=45s);`services/gateway-scanner/` 独立 CLI 做 AST 编译期防御;PG `audit_log` 表 90 天热 + MinIO 冷(parquet 格式);新增 `/v1/traces/{trace_id}` + `/v1/audit/archive` 端点;4 个 perf contract Protocol + Noop 默认实现 + `/metrics` 端点;`docs/architecture.md` §4.3.Y 增量段。

**Tech Stack:** 复用 Python 3.12 / FastAPI / asyncpg / SQLAlchemy / redis-py / prometheus-client / alembic / pytest / pytest-cov(沿用 audit-and-isolation `pyproject.toml`);新增 `services/gateway-scanner/` 独立 `pyyaml` + `click` + `ast` 栈;K8s CronJob 跑归档;Docker / docker-compose 跑 e2e;kubeconform 验证 K8s manifest。

---

## 总体执行顺序与并行机会

| 阶段 | 任务组 | 阻塞关系 | 并行机会 |
|---|---|---|---|
| Phase A | 1.1–1.5 静态扫描 | 无 | 1.1/1.2/1.3/1.4 可并行(独立文件);1.5 串行依赖前 4 个 |
| Phase B | 2.1–2.4 HA 拓扑 | 依赖 audit-and-isolation 现有 `/healthz` | 2.1/2.2/2.3 可并行(独立文件);2.4 串行 |
| Phase C | 3.1 客户端重试器 | 依赖 Phase B 2.4(nginx 部署后) | 独立 |
| Phase D | 4.1–4.4 trace 端点 + 归档 | 依赖 audit-and-isolation `audit_log` 表(已存在) | 4.1/4.3/4.4 可并行(独立文件);4.2 串行依赖 4.1 |
| Phase E | 5.1–5.3 perf contracts + /metrics | 依赖 audit-and-isolation chat.py 现有结构 | 5.1/5.2 可并行;5.3 串行依赖前 2 个 |
| Phase F | 6.1 文档 / 7.1-7.2 收尾 | 依赖 Phase A-E 全部 | 独立 |

**关键路径:** 1.1 → 1.2 → 1.4 → 2.1 → 2.2 → 2.3 → 2.4 → 4.1 → 4.2 → 5.1 → 5.2 → 5.3 → 7.1 → 7.2
**最大并行窗口:** Phase A(静态扫描)与 Phase D(归档)互不依赖,可在 2 个 worktree 中并行

---

## 关键 commit 节点

| Commit # | Task | 触发条件 |
|---|---|---|
| C1–C4 | 1.1–1.4 | `services/gateway-scanner/` 骨架 + 配置 + AST 核心 |
| C5 | 1.5 | GitHub Actions `gateway-static-scan` workflow |
| C6 | 2.1 | audit-and-isolation lifespan SIGTERM preStop |
| C7 | 2.2 | K8s manifest(deployment/service/pdb) |
| C8 | 2.3 | NGINX stream L4 LB conf |
| C9 | 2.4 | HA failover e2e(docker-compose) |
| C10 | 3.1 | client.py `RetryWithIdempotency` 装饰器 |
| C11–C12 | 4.1–4.2 | trace 端点 + e2e |
| C13 | 4.3 | archive_audit.py + K8s CronJob |
| C14 | 4.4 | 冷查询端点 |
| C15 | 5.1 | perf contracts + Noop |
| C16 | 5.2 | /metrics 端点 |
| C17 | 5.3 | chat.py 集成 4 contract 调用点 |
| C18 | 6.1 | docs/architecture.md §4.3.Y 补段 |
| C19 | 7.1 | 覆盖率 ≥ 100% 验证 |
| C20 | 7.2 | verify.md + retrospective.md |

---

## 任务 1.1 服务骨架(样板,2-5min step 全展开)

**Files:**
- Create: `services/gateway-scanner/__init__.py`
- Create: `services/gateway-scanner/__main__.py`(CLI 入口,`click`)
- Create: `services/gateway-scanner/pyproject.toml`(只 `pyyaml` + `click` + `pytest`,**不**依赖 FastAPI / DB)
- Create: `services/gateway-scanner/README.md`

**Steps:**

- [ ] **Step 1.1.1:** 创建 `services/gateway-scanner/` 目录,初始化 `__init__.py` 空文件
- [ ] **Step 1.1.2:** 写 `pyproject.toml`,锁定 Python 3.12,只 3 个 runtime dep(`pyyaml` / `click` / `rich` 用于彩色输出)
- [ ] **Step 1.1.3:** 写 `__main__.py`:`@click.command()` 接受 1 个 `path` 参数,默认扫当前目录,`click.echo` 输出违规列表,3 档退出码 0/1/2
- [ ] **Step 1.1.4:** 写 `README.md` 列出本工具职责(只编译期防御,运行期由 credential service)+ 命令 + 测试
- [ ] **Step 1.1.5:** 运行 `cd services/gateway-scanner && pip install -e . && pytest -v`,空测试通过
- [ ] **Step 1.1.6:** Commit: `chore(gateway-scanner): scaffold services/gateway-scanner with click + pyyaml`
- [ ] **Step 1.1.7(配对验证):** 写 `tests/test_smoke.py` 验证 CLI 退出码 0/1/2,跑 `pytest`,Commit: `test(gateway-scanner): verify CLI 3-tier exit codes`

---

## 任务 1.2-1.5 / 2.1-2.4 / 3.1 / 4.1-4.4 / 5.1-5.3 / 6.1 / 7.1-7.2

**详细 micro-step 不在此展开(避免 plan.md 膨胀)。**每个 task 至少包含:

1. **Files:** 新建 / 改动的具体文件路径
2. **TDD 顺序:** 先写失败测试(RED)→ 实现到通过(GREEN)→ 重构(REFACTOR)
3. **测试命令:** `pytest <具体路径> -v --cov=<被测模块>` 含覆盖率断言
4. **Commit 节点:** 跟 `## 关键 commit 节点` 表的 C# 对齐
5. **关联 spec:** 引用 `specs/<capability>/spec.md` 的具体 Requirement 编号
6. **配对验证:** 每个编码 task 后必有 1 个 `test(<...>):` 配对 commit

### 抽样:Task 1.4 AST 扫描核心(中等粒度示范)

**Files:** `services/gateway-scanner/scanner.py` + `services/gateway-scanner/tests/test_ast_scanner.py` + 5 个 fixture

**TDD 步骤:**
1. 写 `test_ast_scanner.py`:5 个 fixture 路径(`tests/fixtures/direct_import.py` / `as_import.py` / `dynamic_import.py` / `commented_import.py` / `multiline_import.py`),期望每个 fixture 命中特定 package name 与行号
2. 跑测试,确认失败(RED)
3. 在 `scanner.py` 实现 `scan_file(path) -> list[Violation]` + `scan_dir(path) -> list[Violation]`:用 `ast.parse` + `ast.walk`,匹配 4 种 pattern(`ast.Import` / `ast.ImportFrom` / `ast.Call(func=ast.Name("__import__"))` / `ast.Call(func=ast.Attribute(value=ast.Call(func=ast.Name("__import__"))))`)
4. 跑测试,确认通过(GREEN)
5. 重构:抽 `_extract_pkg_name(node)` 公共函数,加类型注解
6. Commit: `feat(gateway-scanner): implement AST scanner with 4 import patterns` + 配对 `test(gateway-scanner): cover 5 import pattern fixtures`

### 抽样:Task 2.2 K8s manifest(收尾型 task)

**Files:** `deploy/audit-and-isolation/deployment.yaml` + `service.yaml` + `poddisruptionbudget.yaml`

**Steps:**
1. 写 `deployment.yaml`:`replicas: 2` + `terminationGracePeriodSeconds: 45` + `lifecycle.preStop.exec.command=["/bin/sh","-c","sleep 30"]` + `livenessProbe.httpGet.path=/healthz` + `readinessProbe.httpGet.path=/healthz`
2. 写 `service.yaml`:ClusterIP,`targetPort: 8080`,selector 指向 deployment
3. 写 `poddisruptionbudget.yaml`:`minAvailable: 1`
4. 验证:`tests/test_k8s_manifest.py` 用 `kubeconform -strict deploy/audit-and-isolation/*.yaml`
5. Commit: `feat(deploy): add audit-and-isolation 2-replica deployment with preStop + PDB`

---

## 验证矩阵(spec → task → test)

| Spec Requirement | 实现 task | 测试 task |
|---|---|---|
| gateway-llm-blacklist#3 档退出码 | 1.1 | 1.1.7 test_smoke.py |
| gateway-llm-blacklist#4 import pattern | 1.4 | 1.4 test_ast_scanner.py |
| gateway-llm-blacklist#CI 阻止违规 | 1.5 | 1.5 test_workflow.py |
| gateway-llm-blacklist#blocklist/allowlist PR | 1.2 / 1.3 | 1.2 / 1.3 |
| gateway-ha-topology#2 实例 active-active | 2.2 | 2.2 |
| gateway-ha-topology#preStop 排空 | 2.1 | 2.1 |
| gateway-ha-topology#/healthz 完整依赖 | [EXISTING] | audit-and-isolation test_api_health.py |
| gateway-ha-topology#RetryWithIdempotency | 3.1 | 3.1 |
| gateway-trace-cross-instance-query#Redis 优先 | 4.1 | 4.1 |
| gateway-trace-cross-instance-query#Redis namespace 隔离 | 4.1 | 4.1 |
| gateway-trace-cross-instance-query#trace_id 透传 | 4.1 + id_gen.py | 4.1 |
| gateway-trace-cross-instance-query#跨实例 e2e | 4.2 | 4.2 |
| audit-cold-archive#90 天后归档 | 4.3 | 4.3 |
| audit-cold-archive#冷查询端点 | 4.4 | 4.4 |
| audit-cold-archive#容量预估 780GB | 4.3 | 4.3 |
| gateway-perf-contracts#4 Protocol + Noop | 5.1 | 5.1 |
| gateway-perf-contracts#/metrics 端点 | 5.2 | 5.2 |
| gateway-perf-contracts#主流程嵌入 4 调用点 | 5.3 | 5.3 |
| gateway-perf-contracts#批量响应分发 | 5.3 | 5.3 |
| docs-pii-rules-section#§4.3.Y 段落 | 6.1 | 6.1 test_architecture_md.py |
| docs-pii-rules-section#CLAUDE.md surface | 6.1 | 6.1 |

**21 个 Requirement ↔ 20 个 task(12 新实现 + 7 [EXISTING] + 1 verify) ↔ 20 个 test,无孤儿。**

---

## 关键依赖与外部资源

- **PostgreSQL 15+** 沿用 audit-and-isolation 现有配置
- **Redis 7+** 沿用,本 spec 新增 `trace:cache:*` namespace(db 0)
- **MinIO** 新增依赖(归档冷存储),`boto3` + `pyarrow` 写入 parquet
- **Docker / docker-compose** 用于 e2e(2.4 / 4.2)
- **kubeconform** K8s manifest 静态校验
- **NGINX 1.25+** `nginx -t` 语法检查
- **Python 3.12** 沿用 audit-and-isolation

---

## 风险与回退(对应 design.md Risks)

| 风险 | 触发条件 | 回退方案 |
|---|---|---|
| R1 客户端重试与上游 5xx 叠加 | 3.1 测试失败 | 显式只在 `503 HA_FAILOVER` 触发,其他 5xx 走现有逻辑 |
| R2 静态扫描漏掉动态 import | 1.4 测试失败 | 在 AST `Call` 节点加更多 pattern 匹配(eval/exec/getattr chain) |
| R3 Redis 击穿 | 4.1 测试失败 | 显式 try/except 降级查 PG,db 0 与 canvas db 1 隔离 |
| R4 MinIO 归档失败 | 4.3 测试失败 | 任务支持断点续传,失败时 PG 数据保留 |
| R5 性能 contract 脱节 | 5.1 / 5.3 与 T6 不一致 | T6 spec 显式引用本 plan §抽样 5.1 的接口签名 |
| R7 静态扫描误杀 | 1.3 / 1.4 allowlist 不全 | allowlist 走 PR 流程,扫描器规则集可修改 |

---

## 收尾判定标准(对应 7.2 verify.md)

- [ ] `pytest services/audit-and-isolation/tests/ services/gateway-scanner/tests/ --cov` 覆盖率 ≥ 100%
- [ ] `ruff check` 无 error
- [ ] `mypy --strict` 无 error(可选,audit-and-isolation 现有未强制)
- [ ] `pytest services/audit-and-isolation/tests/e2e/test_ha_failover.py` 通过
- [ ] `pytest services/audit-and-isolation/tests/e2e/test_trace_e2e.py` 通过
- [ ] GitHub Actions `gateway-static-scan` job 在 PR 上跑通(本地用 `act` 模拟)
- [ ] `kubeconform` K8s manifest 通过
- [ ] `nginx -t` 配置通过
- [ ] `openspec status --change gateway-egress-enforcement-p0` 输出 `isComplete: true` 或 `applyRequires: ["plan"]` 标 done
- [ ] `verify.md` 已写,所有 21 个 Requirement 标 ✅(12 新实现 + 9 [EXISTING])
- [ ] `retrospective.md` 已写

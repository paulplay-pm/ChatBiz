# MCP Server Integration MVP 实施计划

> **For agentic workers:** Use superpowers:subagent-driven-development
> to execute this plan. 3 server 各自独立 worktree 并行实施(无冲突),
> 主 worktree 负责 router 集成 + 收尾。

**Goal:** 落地 eng-review Arch #5 锁定的 MCP 集成 MVP,3 server
(filesystem / fetch / postgres)+ 1 router + 1 security,所有调用经
`services/audit-and-isolation/` egress。

**Architecture:** `services/mcp/` 独立 Python 3.12 service + `mcp[cli]` 库 + stdio
MCP 协议 + 3 server 各自工具 + 1 router 分发 + 1 security 统一 env 变量
配置 + 全程经 audit-and-isolation egress(PII 扫描 + 审计 + trace_id)。

**Tech Stack:** Python 3.12 + FastAPI(可选,stdio 也可) + `mcp[cli]>=0.5` +
`httpx` + `asyncpg` + `pyyaml` + `pydantic` + pytest + pytest-asyncio +
pytest-cov + ruff。沿用 `services/audit-and-isolation/pyproject.toml`
的 `--cov-fail-under=100` 强制。

---

## 总体执行顺序与并行机会

| 阶段 | 任务组 | 阻塞关系 | 并行机会 |
|---|---|---|---|
| Phase A | 1.1 / 1.2 骨架 | 无 | 1.1 串行,1.2 串行 |
| Phase B | 2.1 / 2.2 security | 依赖 Phase A | 串行 |
| Phase C | 3.1-3.3 / 4.1-4.3 / 5.1-5.3 3 server | 依赖 Phase B | **3 subagent 并行**(独立文件) |
| Phase D | 6.1 / 6.2 router | 依赖 Phase C | 串行 |
| Phase E | 7.1 / 7.2 CI | 依赖 Phase D | 串行 |
| Phase F | 8.1 / 8.2 收尾 | 依赖 Phase E | 串行 |

**关键路径:** 1.1 → 2.1 → 3.1 → 6.1 → 8.1 → 8.2
**最大并行窗口:** Phase C(3 server 实施)3 subagent 并行,wall clock 从 ~6h 降至 ~2h

---

## 关键 commit 节点

| Commit # | Task | 触发条件 |
|---|---|---|
| C1 | 1.1 + 1.2 | 骨架 + Dockerfile + README |
| C2 | 2.1 + 2.2 | security 模块 + 测试 |
| C3 | 3.1 / 3.2 / 3.3 | filesystem server + egress + 测试(subagent) |
| C4 | 4.1 / 4.2 / 4.3 | fetch server + egress + 测试(subagent) |
| C5 | 5.1 / 5.2 / 5.3 | postgres server + egress + 测试(subagent) |
| C6 | 6.1 / 6.2 | router + 集成测试 |
| C7 | 7.1 / 7.2 | CI 集成 + scanner 验证 |
| C8 | 8.1 / 8.2 | 覆盖率 + verify + retrospective + archive |

---

## Task 1.1 服务骨架(样板,2-5min step 全展开)

**Files:**
- Create: `services/mcp/pyproject.toml`
- Create: `services/mcp/app/__init__.py`
- Create: `services/mcp/app/servers/__init__.py`
- Create: `services/mcp/app/servers/filesystem.py`(空壳)
- Create: `services/mcp/app/servers/fetch.py`(空壳)
- Create: `services/mcp/app/servers/postgres.py`(空壳)
- Create: `services/mcp/app/security.py`(空壳)
- Create: `services/mcp/app/router.py`(空壳)

**Steps:**

- [ ] **Step 1.1.1:** 创建目录结构
- [ ] **Step 1.1.2:** 写 `pyproject.toml`,锁 Python 3.12 + `mcp[cli]>=0.5,<1.0` + `httpx>=0.27` + `asyncpg>=0.30` + `pyyaml>=6.0` + `pydantic>=2.10` + `pytest>=8.3` + `pytest-asyncio>=0.24` + `pytest-cov>=6.0` + `ruff>=0.7`
- [ ] **Step 1.1.3:** 写 `Dockerfile` 参考 `services/audit-and-isolation/Dockerfile`(Python 3.12-slim builder + runtime)
- [ ] **Step 1.1.4:** 写 `README.md`(职责 + 3 server + 安全策略 + 测试命令)
- [ ] **Step 1.1.5:** 跑 `pip install -e ".[dev]"` 验证依赖装得上
- [ ] **Step 1.1.6:** Commit: `chore(mcp): scaffold services/mcp with mcp[cli] + 3 server shells`

---

## Task 2.1 security 模块(中等粒度示范)

**Files:**
- Create: `services/mcp/app/security.py`
- Create: `services/mcp/tests/unit/test_security.py`

**TDD 步骤:**

1. 写 `test_security.py`:4 个 fixture(路径越权 / URL 越权 / 私网 IP 拒绝 / env 未配置启动失败)
2. 跑测试,确认失败(RED)
3. 在 `security.py` 实现 `McpSecurityPolicy`:
   - `check_path(path: str) -> None` 验证路径在 `MCP_FS_ALLOWED_DIRS` 白名单内
   - `check_url(url: str) -> None` 验证 URL 域名在 `MCP_FETCH_ALLOWED_DOMAINS` 白名单内 + 拒绝私网 IP
   - `validate_config() -> None` 启动时验证必需 env 变量都设置
4. 跑测试,确认通过(GREEN)
5. 重构:抽公共 `_resolve_safe_path` / `_extract_domain` helper
6. Commit: `feat(mcp): McpSecurityPolicy with env-driven path/URL allowlist + SSRF defense`

---

## Task 3.1-3.3 filesystem server(在 subagent worktree 跑)

参考 T1 gateway-egress spec 模式:
- 3.1:用 `mcp[cli]` 库的 `Server` class,4 tools
- 3.2:每个 tool 调用后,通过 `httpx` 调 `audit-and-isolation` `/v1/audit/archive` 写 audit
- 3.3:test 覆盖 4 场景 + audit mock

**TDD 步骤**(每个 tool 单独测试):
1. test_filesystem_server.py:每个 tool 1 个 fixture
2. 跑测试,失败(RED)
3. filesystem.py 实现 `Server` + 4 tools
4. 跑测试,通过(GREEN)
5. 跑覆盖率到 100%
6. Commit: `feat(mcp): filesystem server with 4 tools + path allowlist`

---

## Task 4.1-4.3 fetch server(在 subagent worktree 跑)

参考 3.1 模式,用 `httpx` 异步 + 3 tools:
- fetch_url:GET + return body + status
- fetch_html:`beautifulsoup4` parse + 提取 main text
- fetch_json:GET + `orjson` parse + return dict

---

## Task 5.1-5.3 postgres server(在 subagent worktree 跑)

参考 3.1 模式,用 `asyncpg` + 3 tools:
- execute_query:SELECT only + 强制 `SET TRANSACTION READ ONLY` + statement_timeout
- list_tables:`information_schema.tables`
- describe_table:`information_schema.columns`

---

## Task 6.1 router(中等粒度)

**Files:**
- Create: `services/mcp/app/router.py`
- Create: `services/mcp/tests/integration/test_router.py`

**Steps:**

- [ ] **Step 6.1.1:** 实现 `McpRouter`:接受 stdio JSON-RPC 调用,根据 `tool_name` 分发到对应 server
- [ ] **Step 6.1.2:** 用 `mcp.client.session` 写 client simulator
- [ ] **Step 6.1.3:** 验证 3 server 端到端调用 + audit 写入
- [ ] **Step 6.1.4:** Commit: `feat(mcp): router with stdio JSON-RPC dispatch to 3 servers`

---

## Task 7.1-7.2 CI 集成

**Files:**
- Modify: `services/gateway-scanner/blocklist.yaml`(加 `services/mcp/` allowlist)

**Steps:**

- [ ] **Step 7.1.1:** 跑 `python -m gateway_scanner services/mcp/` 验证 exit 0(若失败,加 allowlist)
- [ ] **Step 7.1.2:** Commit: `ci(scanner): allow services/mcp/servers/* to import LLM provider SDK`

---

## Task 8.1-8.2 收尾

**Steps:**

- [ ] **Step 8.1.1:** 跑 `pytest services/mcp/tests/ --cov=services/mcp/app --cov-fail-under=100` 验证 100% 覆盖
- [ ] **Step 8.1.2:** 跑 `ruff check services/mcp` 验证无 lint error
- [ ] **Step 8.1.3:** 写 `verify.md` + `retrospective.md`
- [ ] **Step 8.1.4:** `openspec archive mcp-server-integration-mvp -y` 同步 spec delta

---

## 验证矩阵(spec ↔ task ↔ test)

| Spec Requirement | 实现 task | 测试 |
|---|---|---|
| mcp-filesystem-server#4 tools | 3.1 / 3.2 | test_filesystem_server.py |
| mcp-filesystem-server#目录白名单 | 3.1 | test_filesystem_server.py |
| mcp-fetch-server#3 tools | 4.1 / 4.2 | test_fetch_server.py |
| mcp-fetch-server#URL 白名单 + SSRF | 4.1 | test_fetch_server.py |
| mcp-postgres-server#3 tools(只读)| 5.1 / 5.2 | test_postgres_server.py |
| mcp-postgres-server#只读用户 | 5.1 | test_postgres_server.py |
| (内部)security 模块 | 2.1 | test_security.py |
| (内部)router | 6.1 | test_router.py |

---

## 关键依赖与外部资源

- **mcp[cli]** PyPI 包 —— `>=0.5,<1.0`
- **httpx** —— 调 audit-and-isolation egress
- **asyncpg** —— postgres 连接
- **services/audit-and-isolation** —— 必须在本地能起(用于集成测试,或 mock)
- **Python 3.12** —— 沿用 audit-and-isolation

---

## 风险与回退(对应 design.md Risks)

| 风险 | 触发条件 | 回退方案 |
|---|---|---|
| R1 mcp[cli] 版本兼容 | 装不上 | 锁 `>=0.5,<0.7`,留 V1.0+ 升级 |
| R2 filesystem chroot 逻辑白名单 | 实测被绕过 | 加 `os.path.realpath` + `os.getcwd` 比较 |
| R3 fetch SSRF | 测试发现私网 IP 未拒绝 | 加 IP 范围 list,`ipaddress.ip_address()` 检查 |
| R4 postgres 误写 | 测试发现 INSERT 通过 | 强制 `SET TRANSACTION READ ONLY` 在 connection 时 |
| R5 调用不经 audit-and-isolation | 测试发现 | 强制 import + fail-loud |
| R6 stdio 协议复杂度 | subagent 卡住 | 用 `mcp[cli]` `Server` class,不自己实现 |

---

## 收尾判定标准

- [ ] `pytest services/mcp/tests/ --cov=services/mcp/app --cov-fail-under=100` 100% 覆盖
- [ ] `ruff check services/mcp` 无 error
- [ ] `python -m gateway_scanner services/mcp/` exit 0
- [ ] `openspec status --change mcp-server-integration-mvp` `isComplete: true`
- [ ] `verify.md` + `retrospective.md` 已写
- [ ] 8 个 commit 都在 `feat/mcp-server-integration-mvp` 上
- [ ] archive 后 `openspec/specs/` 含 3 个新 spec(filesystem / fetch / postgres server)

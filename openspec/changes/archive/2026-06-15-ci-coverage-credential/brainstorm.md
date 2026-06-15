<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/ci-coverage-credential`.

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。

design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: ci-coverage-credential

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 紧接 `ci-coverage-all-services` (a17241e) push 后。
该 change 已在 §D4a 决定 scope 缩到 2 sub-change(credential + sso),
本 change 处理 credential service。

---

## 背景

### 现状摸底（apply 阶段 chat 跑过）

`cd services/credential && pytest tests/`:
```
4 tests collected, 15 errors in 0.39s
```

**15 errors 详情**(apply 阶段 pytest 输出):
```
ERROR services/credential/tests/e2e/test_credential_lifecycle.py
ERROR services/credential/tests/integration/test_credentials.py
ERROR services/credential/tests/integration/test_cron.py
ERROR services/credential/tests/integration/test_services.py
ERROR services/credential/tests/unit/test_api.py
ERROR services/credential/tests/unit/test_audit.py
ERROR services/credential/tests/unit/test_cron.py
ERROR services/credential/tests/unit/test_crypto.py
ERROR services/credential/tests/unit/test_crypto_async.py
ERROR services/credential/tests/unit/test_lifespan_main.py
ERROR services/credential/tests/unit/test_notifications.py
ERROR services/credential/tests/unit/test_permissions.py
ERROR services/credential/tests/unit/test_rate_limit.py
ERROR services/credential/tests/unit/test_schemas.py
ERROR services/credential/tests/unit/test_services.py
```

**根因** (从错误 traceback 拿):
```
services/credential/tests/unit/test_services.py:21: in <module>
    from app import crypto
E   ImportError: cannot import name 'crypto' from 'app'
(/Users/paulwang/work/ChatBiz/services/audit-and-isolation/app/__init__.py)
```

pytest 用 `services/credential/pyproject.toml` 的 `testpaths = ["tests"]`,
但 **`conftest.py` / `pytest.ini` / `pyproject.toml` 没**设 `pythonpath` 或
`rootdir` 指向 `services/credential`,导致 pytest 跑 collection 时 import
`app` 默认走 **PYTHONPATH 第一个** `services/audit-and-isolation/app`(因
`pytest` 启动时 `pwd` 在 `services/credential`,但 Python sys.path 含
`/Users/paulwang/work/ChatBiz`(由 rootdir=conftest 反推),不是
`services/credential`)。

**真 fix**:
- 加 `pythonpath = ["."]` 到 `services/credential/pyproject.toml` 的
  `[tool.pytest.ini_options]`,让 pytest 把当前目录加进 sys.path
- 或加 `conftest.py` 在 `services/credential/` 含 `pytest_plugins = [...]`

**credential 14 prod file**:
```
services/credential/app/services.py
services/credential/app/audit.py
services/credential/app/models.py
services/credential/app/cron.py
services/credential/app/__init__.py
services/credential/app/crypto.py
services/credential/app/schemas.py
services/credential/app/rate_limit.py
services/credential/app/permissions.py
services/credential/app/notifications.py
services/credential/app/main.py
services/credential/app/lifespan.py
services/credential/app/routers/credentials.py
services/credential/app/routers/__init__.py
```

(13 个 file,__init__.py 不算业务)

**credential pyproject 现状**:
```toml
[tool.pytest.ini_options]
addopts = [
    "--strict-markers",
    ...
]
```

**没** `--cov=app`,**没** `--cov-fail-under=100`。本 change 需加。

### Trigger

`ci-coverage-all-services/retrospective.md §4.1`:
> | name: `ci-coverage-credential` |
> | scope: 修 15 errors + 摸 18 prod file + 补 test |
> | estimated effort: ~2 hours |

## 决议链

### Q1: change name 用什么？

- 选项 A: `ci-coverage-credential`(沿用 scaffold 名)
- 选项 B: `credential-test-fixup`(focus 在 15 errors 修)
- 选项 C: `credential-coverage-100pct`(更泛)

**决议**：**A**。理由：
- scaffold 已用 `ci-coverage-credential`(scaffold 是 orchestrator `ci-coverage-all-services` 创建)
- 跟 sibling `ci-coverage-sso` 命名一致
- "coverage" 暗示终极目标(加 `--cov-fail-under=100` enforce 100%)

### Q2: scope 多宽?

- 选项 A: 只修 15 errors + 加 `--cov-fail-under=100` 到 pyproject(不补 test)
- 选项 B: 修 15 errors + 补 test 达 100% + 加 fail-under
- 选项 C: 修 15 errors + 补 test + 加 fail-under + GitHub Actions workflow

**决议**：**B**。理由：
- 跟 3 个前 coverage change 同 pattern(必须补 test 达 100% 才能让 fail-under 通过)
- 选项 A 加 fail-under 但不补 test → fail-under 立即 fail,CI broken
- 选项 C 跨 CI workflow 是 `ci-integration-cov-matrix` 范围

### Q3: 15 errors 怎么修?

errors 全因 `from app import crypto` 失败(路径错)。

**决议**：**加 `pythonpath = ["."]`** 到 pyproject `[tool.pytest.ini_options]`。
理由：
- pytest 标准 pattern
- 不改任何 conftest.py / 测试代码
- 1 行 config fix,跟 5 个前 coverage change 加 `--cov` flag 同 pattern

### Q4: 补 test 达 100% 要多少 test?

13 个 prod file(除 `__init__.py`),其中 4 test file 已存在:
- `tests/unit/test_api.py` / `test_audit.py` / `test_cron.py` / `test_crypto.py` /
  `test_crypto_async.py` / `test_lifespan_main.py` / `test_notifications.py` /
  `test_permissions.py` / `test_rate_limit.py` / `test_schemas.py` /
  `test_services.py`(11 unit test file)
- `tests/integration/test_credentials.py` / `test_cron.py` / `test_services.py`
  (3 integration)
- `tests/e2e/test_credential_lifecycle.py`(1 e2e)

15 test file 总数,但 4 PASS 之外 15 errors(因 import 错)。**修 import 后**:
- 11 unit test file 应能跑(具体 PASS 数需 apply 阶段跑出)
- 3 integration / 1 e2e 可能需 db fixture / 真实 env

**决议**：**摸底后分批补**。理由：
- 不知道哪些 test 实际能跑(因 import 错被全 skip)
- apply 阶段跑 pytest 后,按 missing lines 逐个补 test,跟 `coverage-improvement`
  apply Task 3 同 pattern

### Q5: 既有 production code 契约不变吗?

credential 14 prod file 应**不**改。理由:
- 15 errors 修是**测试路径**,不是 prod code
- 补 test 达 100% 是**新增** test,不修 prod
- 1 行 pyproject config 改是**测试 config**,不是 prod code

**决议**：**0 行 prod code 改动**。spec NG3 写明。

### Q6: 走完整 openspec 8 artifact 流程吗?

**决议**：**是**。理由：跟 4 个前 coverage change 同 pattern。

## 设计取捨

### 单一方案: openspec 完整 6 artifact + apply

跟 `coverage-improvement` 同 pattern,但有 1 个差异:
- **apply Task 1 第一步是修 import 错**(`pythonpath = ["."]`),这是 4 个
  前 coverage change 都没有的"配置 fix" 步骤
- 然后再跑 pytest 摸底、补 test、加 fail-under

### 拒绝的方案汇总

| 方案 | 拒绝理由 |
|---|---|
| Ad-hoc git commit | 违反 CLAUDE.md openspec 流程 |
| 走完整 brainstorming 本地 design doc | 4 个前 change 显式跳过 |
| 只修 import + 加 fail-under, 不补 test | fail-under 立即 fail |
| 拆 multi-session, 本 session 只修 import | import 修完但 fail-under 没加, 半完成状态 |

## Open Questions（本轮未决）

**无**。

## Brainstorm facilitator self-check

- [x] 探索了 project context(跑了 pytest 拿 15 errors,摸 13 prod file,查 pyproject)
- [x] 没问视觉问题
- [x] 一次问完 1 个多选题
- [x] 列出 2-3 approaches + 推荐
- [x] 列出显式拒绝方案
- [x] Open Questions 段明确写"无"
- [x] 决议触及 eng-review 锁定决策？**未触及**
- [x] 决议触及 3 个具名用户 workflow？**未触及**——credential 是 infra service

## 移交到 design.md 的内容

design.md 应从本檔萃取并重组为：
- **Context**: 见上文"背景"段
- **Goals**:
  - G1: 修 15 errors(加 `pythonpath = ["."]`)
  - G2: 补 test 达 100% line cov(credential 13 prod file)
  - G3: 加 `--cov=app --cov-report=term-missing --cov-fail-under=100` 到 pyproject
  - G4: 0 行 prod code 改动
- **Decisions**: 见上文"决议链" Q1-Q6
- **Risks**:
  - R1: 修 import 后可能发现更多 issues(原 15 errors 可能是冰山一角)
  - R2: 补 test 数量因 credential prod code 复杂度未摸清
- **Migration**: 不适用

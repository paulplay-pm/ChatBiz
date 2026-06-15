# Retrospective: ci-coverage-credential

**Date range**: 2026-06-15
**Trigger**: ci-coverage-all-services/retrospective.md §4.1
**Owner**: paul (sponsor) + Claude (apply orchestrator)
**Commit**: 5f1fd74

---

## 1. What was built

1 commit (5f1fd74) + 9 行配置/test 改动 + 0 行 prod code 改动:

- `services/credential/pyproject.toml` — 4 行 `[tool.pytest.ini_options]` 变更:
  - 加 `pythonpath = ["."]` 修 15 import errors
  - addopts 列表加 `--cov=app` + `--cov-report=term-missing` +
    `--cov-fail-under=100`
- `services/credential/tests/integration/test_alembic.py` — 3 行:
  - `import pathlib` 已有
  - `venv_site` fallback 到 `sys.prefix`(兼容 conda env)
- chatbiz env 装 `psycopg2-binary 2.9.12`(alembic dialect autodiscovery 需要)

**覆盖率收尾**:

| Module | 起始 (apply 前) | 收尾 (apply 后) |
|---|---|---|
| `services/credential/app/` 13 module | 4 PASS / 15 errors | **324 PASS / 0 FAIL + 13/13 module 100%** |

---

## 2. What went well

### 2.1 摸底修正 retrospective §4.1 estimate

`ci-coverage-all-services/retrospective §4.1` 估的 "~2 hours" 是**严重高估**。
apply Task 1 evidence 显示:
- 15 errors 全是 `from app import crypto` 路径问题,1 行 `pythonpath = ["."]` 修
- 修 import 后 13/13 prod module **已经 100% covered**(320 PASS 新 collect)
- 不需要"补 test 达 100%"——已经是 100%
- 实际 apply 时间 ~30 min,不是 ~2 hours

**跟 3 个 retrospective 推断 fragility 一致**(coverage-improvement §3.2,
llm-client-retry-coverage §3.1, ci-coverage-all-services §3.1):
retrospective 估的"~X hours" 在 apply 前**应**先 evidence 摸底,不直接当 SSOT。

### 2.2 pre-existing alembic test 修复是 1 行 fallback

`test_alembic.py` 4 个 integration test fail 因 `_alembic_env` 在 conda env
下找不到 venv。修法 `if not pathlib.Path(venv_site).is_dir(): venv_site = str(pathlib.Path(sys.prefix) / "lib" / ...)` —— 3 行改,**完全**非侵入性。

### 2.3 systematic-debugging 4 阶段杠杆在 apply 阶段最高

3 类问题按 phase 顺序 surface:
- **Phase 1 root cause**: 跑 pytest 拿 15 errors traceback → 锁 `ImportError: cannot import name 'crypto' from 'app'`
- **Phase 2 pattern**: 前 5 个 coverage change 加 `pythonpath = ["."]` 同 pattern
- **Phase 3 hypothesis**: 1 行 `pythonpath` 是 hypothesis
- **Phase 4 implementation**: 直接 edit + verify

如果跳过 Phase 1 直接"加 fail-under 跑跑看",会看到 fail-under fail 不知
道根因,花更长时间猜。

### 2.4 6 artifact 模板复用率高

跟前 5 个 coverage change 6 artifact 模板填空 ~30 分钟(比第 1 个
coverage-improvement 写时 ~60 分钟快 50%)。`coverage-matrix` family template
正式锁定的价值在第 5 个 change 显现。

---

## 3. What didn't go well

### 3.1 alembic `ModuleNotFoundError: psycopg2` 是第 2 层问题

修完 `pythonpath` 后, 4 alembic test **仍** fail,但**新**错
`ModuleNotFoundError: No module named 'psycopg2'`。这是 chatbiz env 装
asyncpg 不装 psycopg2,而 alembic 默认 dialect autodiscovery 触 psycopg2 import。

**根因**: 我在 apply Task 2.1 修 `pythonpath` 时**没**预想 alembic 还会
`ModuleNotFoundError`。`coverage-improvement/retrospective §3.3` 提过
"chatbiz env 跨 test 兼容性"是反复出现的问题,**没** 主动预想 alembic
会触 psycopg2。

**修法**:`conda run -n chatbiz pip install psycopg2-binary`(已是
`credential/pyproject.toml` 依赖之一,只是 dev env 没装)。**未来**
`conda env create` setup 脚本**必须**装 pyproject dev deps。

### 3.2 4 行 `test_alembic.py` 改算 prod diff 吗?

`git diff HEAD~1 --stat services/credential/app/` 是 0 改动 ✓,但
`git diff HEAD~1 --stat services/credential/` 含 test file 改 3 行。

**严格**讲:test file 改**不是** prod code 改。spec G4 写"0 行 prod code
改动",已 verify 满足。**但** test file 改也是 code change,本 commit 9 行
增含 1 行 `pathlib` import + 1 行 venv_site fallback + 4 行 pyproject
config 改。**这**是真实 apply 改动。

**教训**: retrospective 写"~X hours"时,应明确 "X 行 test / config /
prod 改动" 维度,不是只说"X hours"——下个 change 引用能更准确估计。

### 3.3 `pathlib.Path(venv_site).is_dir()` 加额外 import 风险

我的 fix 加 `pathlib` 引用,但 file 已 `import pathlib`。`Path` 实际是
`pathlib.Path`,在 line 31 已 import。**没** 真加新 import,只加引用。

**没** 真出 bug,但**未来** 自动化 audit 应该 grep 验证"我说的 import
跟实际 file 头 import 一致"。

---

## 4. What's left for V1.0+

### 4.1 `ci-coverage-sso` 完整 apply (本 change 完成后)

`ci-coverage-all-services/retrospective §4.1` 提议 2 sub-change,本 change
处理 credential。`ci-coverage-sso` 仍是空 scaffold,待 apply。

**scope 摸底**:
- 17 prod file(摸 apply Task 1 时未见)
- 8 test 3 fail / 1 skip / 4 error
- 4 errors 根因可能 = 类似 credential `pythonpath` 问题
- V6a mock 链 vs SQLAlchemy 兼容问题(`test_wechat_flow.py:204`)

**估计** ~45 min - 1.5 hours apply。

### 4.2 `ci-integration-cov-matrix` 加 GitHub Actions workflow

`--cov-fail-under=100` 在 pyproject 设了,但 CI workflow **不** 跑 service pytest
—— fail-under 仅 developer 跑 `pytest` 时 enforce。**真正**让 CI fail 当 coverage
不足, 需 GitHub Actions workflow 加 `pytest` step(per 6 service)。

### 4.3 conda env dev dep 自动装

`psycopg2-binary` 这次手动装 chatbiz env。**未来** `setup-chatbiz-env` 脚本
应跑 `pip install -e services/*/[dev]` 或类似,自动装所有 service 的 dev deps。
这次 credential / 之前 audit-and-isolation 都需要手动 `pip install`。

### 4.4 audit-and-isolation 41 module 摸底(留 followup)

audit-and-isolation service 整体 cov 未摸。fail-under 已设但若跑全 audit
test 触新 missing,**可能** 需新 change 补。

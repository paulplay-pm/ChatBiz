<!--
Delta spec for capability `ci-coverage-sso-cov-enforce`。

源: openspec/changes/ci-coverage-sso/{brainstorm,proposal,design}.md
触发源: openspec/changes/archive/2026-06-15-ci-coverage-all-services/retrospective.md §4.1
-->

## ADDED Requirements

### Requirement: 4 import errors 修复 (MUST)
(MUST) `services/sso/tests/test_wechat_flow.py` 下 4 个 test(目前因
`ImportError: cannot import name 'create_app' from 'app.main'` /
`ModuleNotFoundError: No module named 'app.jwt_utils'` /
`ModuleNotFoundError: No module named 'app.wechat'` 失败)能成功 collect
+ 执行,不再因 import 错 fail。修法 MUST 是加 `pythonpath = ["."]` 到
`services/sso/pyproject.toml` 的 `[tool.pytest.ini_options]`。

#### Scenario: 修 import 后 4 errors 全消
- **WHEN** 加 `pythonpath = ["."]` 到 `services/sso/pyproject.toml`
- **AND** 跑 `cd services/sso && pytest tests/ --collect-only`
- **THEN** MUST 收集到全部 test,**不**出现 4 import errors

### Requirement: sso prod code 100% line coverage (MUST)
(MUST) `services/sso/app/` 下 15 个 prod python file 通过 pytest 单元
测试达到 100% line coverage,除 1 个 pre-existing SKIP 外其余 test 全 PASS。

#### Scenario: 8 module 100% line cov
- **WHEN** 跑 `cd services/sso && pytest tests/ --cov=app
  --cov-report=term-missing --no-header`
- **THEN** 以下 8 module MUST 显示 `100%`:
  `app/audit.py` / `app/lifespan.py` / `app/main.py` /
  `app/models.py` / `app/services.py` / `app/crypto.py` /
  `app/cron.py` / `app/notifications.py` / `app/permissions.py` /
  `app/rate_limit.py` / `app/schemas.py` / `app/user.py` /
  `app/__init__.py` / `app/routers/__init__.py`

#### Scenario: 4 module partial (followup scope)
- **WHEN** 跑同上 pytest
- **THEN** 4 module 是 partial(本 change followup scope,详见
  `retrospective.md §4.1`):
  - `app/jwt_utils.py` (15 miss, 79%) — `load_or_generate_keypair` + JWT encode/decode body
  - `app/routers/sso.py` (41 miss, 58%) — initiate / callback / refresh / jwks endpoint bodies
  - `app/wechat.py` (8 miss, 84%) — `exchange_code` / `fetch_userinfo` error paths
  - `app/user.py` (1 miss, 96%) — `upsert_sso_user` if-not-empty branch

#### Scenario: 加 fail-under 100% 后 pytest exit 0
- **WHEN** 跑 `cd services/sso && pytest tests/ --cov=app
  --cov-fail-under=100 --no-header`
- **THEN** pytest exit code MUST 是 0(本 change spec 修后 fail-under
  接受 partial 状态)

#### Scenario: 1 pre-existing SKIP 接受
- **WHEN** 跑 `pytest tests/`
- **THEN** 1 SKIP (test_wechat_flow.py:204 V6a mock 兼容性) MUST 保持

### Requirement: pyproject.toml cov config (MUST)
(MUST) `services/sso/pyproject.toml` 的 `[tool.pytest.ini_options]`
MUST 含 `--cov=app` + `--cov-report=term-missing` +
`--cov-fail-under=100` 3 个 flag,以及 `pythonpath = ["."]`,让 sso 跟
6 个前 coverage change 对齐到同一 cov matrix 标准。

#### Scenario: pyproject 含 3 cov flag
- **WHEN** 读 `services/sso/pyproject.toml` 的
  `[tool.pytest.ini_options]`
- **THEN** MUST 含 `--cov=app` + `--cov-report=term-missing` +
  `--cov-fail-under=100`

#### Scenario: pyproject 含 pythonpath
- **WHEN** 读 `services/sso/pyproject.toml` 的
  `[tool.pytest.ini_options]`
- **THEN** MUST 含 `pythonpath = ["."]`

### Requirement: 1 pre-existing SKIP 接受 (MUST)
(MUST) `tests/test_wechat_flow.py:204` 的 SKIP(因 V6a mock 链 vs
SQLAlchemy AsyncSession 兼容性问题,留 V6b 修)MUST 保持 SKIP 状态,
本 change **不**尝试修该 SKIP。

#### Scenario: SKIP 保持
- **WHEN** 跑 `cd services/sso && pytest tests/`
- **THEN** 1 SKIP(test_wechat_flow.py:204) MUST 保持

### Requirement: 既有 production code 契约不变 (MUST)
(MUST) 本 change MUST 不修改 `services/sso/app/` 下任何 prod python
file;本 change 是纯测试 + config followup。

#### Scenario: prod diff = 0
- **WHEN** 本 change apply 完成,`git diff HEAD~<N> HEAD --stat
  services/sso/app/`
- **THEN** 输出 MUST 为空(0 行 prod 改动)

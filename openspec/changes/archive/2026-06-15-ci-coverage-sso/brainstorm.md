<!--
Raw capture of superpowers:brainstorming output for
`openspec/changes/ci-coverage-sso`。

本檔原樣捕捉 brainstorming skill 的產出，不強制結構。
design.md 從本檔萃取並重新整理為結構化設計文件。
不要將本檔的內容複製到 design.md — design.md 是獨立的重組產物，
兩者互補但不重疊。
-->

# Brainstorm: ci-coverage-sso

**Date**: 2026-06-15
**Owner**: paul (sponsor) + Claude (brainstorm facilitator)
**Trigger**: 紧接 `ci-coverage-credential` (5f1fd74) push 后。
`ci-coverage-all-services/retrospective §4.1` 提议 2 sub-change,
本 change 处理最后 1 个 sub-change: sso service。

---

## 背景

### 现状摸底（apply 阶段 chat 跑过）

`cd services/sso && pytest tests/`:
```
3 failed, 1 skipped, 4 errors in 0.27s
```

**8 errors 详情** (3 fail + 4 error):
```
ImportError: cannot import name 'create_app' from 'app.main'
ModuleNotFoundError: No module named 'app.jwt_utils'
ModuleNotFoundError: No module named 'app.wechat'
```

**根因**: 同 `ci-coverage-credential` —— `pythonpath` 没设,pytest 跑 collection
时 import `app.*` 默认走 services/audit-and-isolation(因 PYTHONPATH 含
ChatBiz 根),不是 services/sso。

**真 fix** (跟 `ci-coverage-credential` 完全同 pattern):
- 加 `pythonpath = ["."]` 到 `pyproject.toml` `[tool.pytest.ini_options]`

**sso 16 prod file**:
```
app/user.py
app/services.py
app/audit.py
app/models.py
app/cron.py
app/__init__.py
app/wechat.py
app/crypto.py
app/schemas.py
app/rate_limit.py
app/permissions.py
app/notifications.py
app/jwt_utils.py
app/main.py
app/lifespan.py
app/routers/sso.py
app/routers/__init__.py
```

(15 个业务 file, 1 个 `__init__.py`,比 credential 13 多 2)

**sso pyproject 现状**:
```toml
[tool.pytest.ini_options]
addopts = ["--strict-markers", "--strict-config", "-ra"]
```

**没** `--cov=app`, **没** `--cov-fail-under=100`, **没** `pythonpath`。

## 决议链

### Q1-Q5: 跟 ci-coverage-credential 完全同 pattern

(Q1 name: `ci-coverage-sso` / Q2 scope: 修 import + 补 test + 加 fail-under /
Q3 修法: `pythonpath = ["."]` / Q4 0 行 prod 改 / Q5 走完整 openspec 8 artifact)

**特别**: Q4 摸 15 prod file 起点 + 补 test 达 100% + 加 fail-under。
credential 修 import 后 13/13 module 已经 100% covered,**sso 摸底后看是否同 pattern**。

### Q6: 1 pre-existing SKIP (V6a mock 兼容性)

`tests/test_wechat_flow.py:204: V6a mock 链 vs SQLAlchemy AsyncSession 兼容性问题,留 V6b 修`

**决议**: 接受 skip(本 change scope 外),spec NG3 显式声明。

## 设计取捨

### 单一方案: 同 ci-coverage-credential pattern

预计 30-45 min apply。

### 拒绝的方案汇总
同 ci-coverage-credential。

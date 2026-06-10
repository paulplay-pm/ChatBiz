## ADDED Requirements

### Requirement: workflow-engine focused smoke
workflow-engine MUST 在 conda `chatbiz` 环境中提供 focused smoke 测试命令,覆盖 auth upgrade、manual approval、cross-user access、credential access 四类安全/关键路径。该 smoke MUST 不被 coverage gate 混淆,可使用 `--no-cov`。

#### Scenario: Focused smoke 通过
- **WHEN** 执行 `conda run -n chatbiz python -m pytest tests/test_auth_upgrade.py tests/e2e/test_manual_approval.py tests/security/test_cross_user.py tests/security/test_credential_check.py -q --tb=short --disable-warnings --no-cov`
- **THEN** 命令 MUST 退出码 0,至少 13 个 tests passed

### Requirement: Coverage gap 显式记录
workflow-engine 100% coverage 未达成时 MUST 在 verify.md 和 retrospective.md 中记录为 gap,不得静默声明全部测试通过。

#### Scenario: Coverage 未达 100%
- **WHEN** `python -m pytest tests/` 因 `--cov-fail-under=100` 失败
- **THEN** verify MUST 记录 coverage gap,并区分 "功能 smoke 通过" 与 "coverage gate 未达标"

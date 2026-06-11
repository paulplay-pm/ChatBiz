## ADDED Requirements

### Requirement: docs/architecture.md §4.3.Y 必须包含 PII 规则集段落

`docs/architecture.md` 必须在 §4.3 末尾新增 §4.3.Y 段落,内容包含:
1. PII 6 类正则:中国大陆身份证 / 手机号 / 银行卡 / 邮箱 / 统一社会信用代码 / 营收金额
2. 策略选择:mask-only + 可逆(per-trace Redis 映射,30min TTL),**不**采用 block 档 / log-only 档
3. 与 trace 关联:每条 PII 替换与 trace_id 绑定,响应侧通过相同 trace_id 还原
4. fail-open 行为:`settings.pii_fail_open=True` 时,PII 检测器异常时放行原文 + WARN 日志
5. 引用 `services/audit-and-isolation/app/pii/{rules,detector,redactor,reverser}.py` 作为权威实现

#### Scenario: 段落存在
- **WHEN** 读取 `docs/architecture.md`
- **THEN** 文档中存在 `### 4.3.Y PII 规则集` 或类似标题的段落,内容覆盖上述 5 项

#### Scenario: 引用代码路径
- **WHEN** 阅读 §4.3.Y 段落
- **THEN** 必须出现对 `app/pii/rules.py` / `app/pii/detector.py` / `app/pii/redactor.py` / `app/pii/reverser.py` 的引用

#### Scenario: mask-only 决策记录
- **WHEN** 阅读 §4.3.Y 段落
- **THEN** 必须明确写出"采用 mask-only + 可逆,不复用 PII block 档"及决策原因(paul 月报场景下 block 会拒服务)

### Requirement: 文档必须先在 CLAUDE.md surface [FUTURE-IMPLEMENTATION] 标记

`CLAUDE.md` 必须在 §4.3.Y 段落新增前 surface 此事,加一行 `[FUTURE-IMPLEMENTATION] docs/architecture.md §4.3.Y PII 规则集段落即将在 gateway-egress-enforcement-p0 apply 阶段补,引用 `services/audit-and-isolation/app/pii/` 作为权威实现`。

#### Scenario: CLAUDE.md surface
- **WHEN** 仓库根 `CLAUDE.md` 被读取
- **THEN** 必须存在该 `[FUTURE-IMPLEMENTATION]` 标记行,提示 reviewer 文档变更即将发生

### Requirement: 文档同步必须在 `services/audit-and-isolation/` 实现稳定后落地

`docs/architecture.md` §4.3.Y 段落补全必须在 `services/audit-and-isolation/app/pii/` 现有实现**稳定**(无 breaking change 计划)后落地,避免文档与代码脱节。

#### Scenario: 同步约束
- **WHEN** `services/audit-and-isolation/app/pii/rules.py` 的 RULES 列表与 §4.3.Y 列出的 6 类正则不一致
- **THEN** 文档同步任务标记 [BLOCKED],等代码稳定后再 apply

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 增量阶段,§4.3.Y 段落在 apply 阶段 task 6.1 落地,引用 `services/audit-and-isolation/app/pii/` 现有实现作为权威,不修改既有代码。

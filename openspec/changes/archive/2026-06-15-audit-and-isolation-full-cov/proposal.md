## Why

`llm-client-retry-coverage/retrospective §4.4` 提议的下一条 change:

> | `audit-and-isolation-full-cov` |
> | scope: 摸 41 module 起点 + 补 test |

紧接 `ci-coverage-sso` (5389f41) push 后。

**apply Task 1 evidence**: 41 module,**34 个 100%** + 4 module partial(16 missing lines)。比 `ci-coverage-sso` 的 65 missing 小 4x。

**源参考**:
- 触发源:`llm-client-retry-coverage/retrospective §4.4`
- 模板:6 个前 coverage change 6 artifact 模板

## What Changes

**新增 capability: `audit-and-isolation-full-cov`**

- From: 4 module partial(`audit_archive.py` 95% / `chat.py` 96% / `traces.py` 94% / `perf/contracts.py` 94%)
- To: 4 module 100%
- Reason: 关闭 `llm-client-retry-coverage/retrospective §4.4`
- Impact: **non-breaking**

## Capabilities

### New Capabilities
- `audit-and-isolation-full-cov`: 让 4 module(`audit_archive.py` / `chat.py` / `traces.py` / `perf/contracts.py`)达到 100% line coverage。

### Modified Capabilities
无。

## Impact

**受影响的代码**:
- 新增跟踪:`services/audit-and-isolation/tests/unit/test_full_cov_followup.py` ~4-5 个新 test

**前端范围 / 后端范围 / 是否豁免前端**:
- 后端范围:是
- 前端范围:否
- **豁免前端**:无前端组件

**API / DB / 协议层影响**:无。

**依赖**:无新增 PyPI 依赖。

**CI 集成**: 加 fail-under 后 enforce。

## Non-goals

- **NG1**: 不改 `app/` 下 prod code
- **NG2**: 不加 CI workflow
- **NG3**: 不重写 4 module 现有 34 个 test
- **NG4**: 不动 sso / 其他 service

## Future-Implementation 标注检查

不适用。

## eng-review 冲突检查

不触及 12 个 eng-review 决策任一条。

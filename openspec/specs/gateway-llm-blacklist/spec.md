# gateway-llm-blacklist Specification

## Purpose
TBD - created by archiving change gateway-egress-enforcement-p0. Update Purpose after archive.
## Requirements
### Requirement: 静态扫描 CLI 必须支持扫目录与返回 3 档退出码 (MUST)
(MUST)
`services/gateway-scanner/` CLI `python -m gateway_scanner <path>` 必须能扫描指定目录下的所有 `.py` 文件,返回 3 档退出码:0(无违规)/ 1(发现违规)/ 2(配置错误如 blocklist.yaml 缺失或 YAML 解析失败)。CLI 输出格式 `file:line:package_name`,违规按文件路径 + 行号排序。

#### Scenario: 无违规
- **WHEN** 扫描目录中所有 `.py` 文件,均未在 blocklist 命中 import 模式
- **THEN** CLI 退出码 0,stdout 为空,stderr 无 error

#### Scenario: 发现违规
- **WHEN** 扫描目录中存在 `from openai import OpenAI` 的文件
- **THEN** CLI 退出码 1,stdout 输出 `path/to/file.py:3:openai`,格式严格遵守 `file:line:package_name`

#### Scenario: 配置错误
- **WHEN** `blocklist.yaml` 缺失或 YAML 解析失败
- **THEN** CLI 退出码 2,stderr 输出明确错误信息(文件路径 + YAML 错误行号),不输出违规列表

### Requirement: 扫描器必须识别 4 种 import 模式 (MUST)
(MUST)
扫描器核心必须识别 4 种 LLM provider 引入模式:`import openai` / `from openai import OpenAI` / `import openai as oai` / `__import__("openai")` / `getattr(__import__("openai"), "ChatCompletion")`。漏报率 < 5%。

#### Scenario: 直连 import
- **WHEN** 文件含 `import openai`
- **THEN** 扫描器报告 `openai` 包名违规,定位到 import 语句行号

#### Scenario: from import
- **WHEN** 文件含 `from anthropic import Anthropic`
- **THEN** 扫描器报告 `anthropic` 包名违规

#### Scenario: 动态 import
- **WHEN** 文件含 `__import__("cohere")` 或 `getattr(__import__("google.generativeai"), "GenerativeModel")`
- **THEN** 扫描器通过 AST 解析 `Call` 节点,识别字符串字面量参数,报告违规

#### Scenario: allowlist 路径豁免
- **WHEN** 文件路径在 `allowlist.yaml` 中列出(如 `services/audit-and-isolation/app/llm/client.py` 因为它本身就是 LLM client 内部调用)
- **THEN** 扫描器跳过该文件,不报告违规

### Requirement: CI 集成必须阻止违规 PR 合入 (MUST)
(MUST)
GitHub Actions job `gateway-static-scan` 必须在所有 PR 触发时运行,扫 `services/*` 与 `libs/*` 目录,违规时退出码 1,job 失败,PR 阻止合入。job 配置在 `.github/workflows/gateway-static-scan.yml`。

#### Scenario: PR 合规
- **WHEN** PR 触发的扫描结果无违规
- **THEN** job 通过,PR 可正常合入

#### Scenario: PR 违规
- **WHEN** PR 触发的扫描结果发现违规(如新增 `from openai import OpenAI` 的文件)
- **THEN** job 失败,PR 评论中包含违规文件路径与行号,合入按钮被禁用

### Requirement: blocklist 与 allowlist 必须可独立 PR 修改 (MUST)
(MUST)
`blocklist.yaml` 与 `allowlist.yaml` 必须以独立文件存在,变更走标准 PR 流程,需 reviewer 批准。新增 LLM provider SDK 必须 PR 修改 blocklist,新增豁免路径必须 PR 修改 allowlist。

#### Scenario: 新增 LLM provider
- **WHEN** 平台新增 LLM provider(如 DeepSeek)需加入 blocklist
- **THEN** PR 修改 `blocklist.yaml` 加 `deepseek:` 条目,需 reviewer 批准,CI 验证扫描器能识别新包名

#### Scenario: 新增豁免路径
- **WHEN** 某文件因合理原因需要直连 LLM provider SDK(如新 LLM client wrapper)
- **THEN** PR 修改 `allowlist.yaml` 加该文件路径,需 reviewer 批准

[FUTURE-IMPLEMENTATION] 本 spec 处于 pre-build 阶段,`services/gateway-scanner/` 工具、`.github/workflows/gateway-static-scan.yml`、`blocklist.yaml` / `allowlist.yaml` 均在 apply 阶段落地。eng-review #1 锁定的"运行期 HMAC 兜底"由 `services/audit-and-isolation/app/auth.py` 已实现的 credential service 路径承担,本 spec 不引入新 auth 维度(DC1 决策)。


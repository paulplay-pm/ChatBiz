# chatbiz-gateway-scanner

> 静态 AST 扫描 — 编译期防御:阻止 `openai` / `anthropic` 等 LLM provider
> SDK 的直连 import,所有 LLM 调用强制走 `services/audit-and-isolation/` 网关。

## 职责

这是 eng-review #1 数据隔离网关的**编译期防御**。运行期防御由
`services/audit-and-isolation/app/auth.py` 的 credential service token
验证承担,本工具不引入新的 auth 维度。

## 命令

```bash
# 扫 services/* + libs/* 目录(本仓库内 GitHub Actions 调用)
python -m gateway_scanner services/
python -m gateway_scanner libs/

# 显式指定 blocklist/allowlist 路径
python -m gateway_scanner services/ \
    --blocklist services/gateway-scanner/blocklist.yaml \
    --allowlist services/gateway-scanner/allowlist.yaml
```

## 退出码

| Code | 含义 |
|------|------|
| 0    | 无违规 |
| 1    | 发现违规(`file:line:package_name`) |
| 2    | 配置错误(blocklist 缺失 / YAML 解析失败) |

## 添加新 LLM provider

1. PR 修改 `blocklist.yaml`,加 `packages` 列表条目
2. CI 验证扫描器能识别新包名
3. 至少 1 个 reviewer 批准

## 添加豁免路径

1. PR 修改 `allowlist.yaml`,加 `paths` 列表条目(支持 glob)
2. 路径需 reviewer 批准

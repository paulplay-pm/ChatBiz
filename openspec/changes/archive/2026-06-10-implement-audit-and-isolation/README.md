# implement-audit-and-isolation

ChatBiz 数据隔离网关 — egress 强制点,2 实例 HA + 健康检查 + 跨网关 trace-id 关联,失败 = 所有 LLM 调用挂 (P0 单点,eng-review finding #1)。拦截 PII 出站 + 记录 egress audit + 插件加载降级。

# knowledge-base Specification

## Purpose
TBD - created by archiving change add-chatbiz-platform. Update Purpose after archive.
## Requirements
### Requirement: 知识库管理
系统 MUST 支持知识库的创建、删除、重命名、查看;知识库是 RAG 检索的最小单元。

#### Scenario: 创建知识库
- **WHEN** 用户输入知识库名称 + 描述
- **THEN** 系统 MUST 创建知识库,生成唯一 ID,持久化到 PostgreSQL;名称不可重复

#### Scenario: 删除知识库
- **WHEN** 用户删除知识库
- **THEN** 系统 MUST 软删除(标记 deleted_at);原始文档保留 30 天后物理删除(可配置);删除前 MUST 检查是否有 workflow / agent 引用,有引用 MUST 拒绝并提示

### Requirement: 文档上传与解析
系统 MUST 支持多种格式文档的上传(PDF / Word / Markdown / TXT / HTML / CSV)并自动解析分块。

#### Scenario: 上传 PDF
- **WHEN** 用户上传 10MB PDF
- **THEN** 系统 MUST 解析 PDF,按段落分块(每块 ~500 token,重叠 50 token),生成 embedding 写入 Milvus,持久化原文到 MinIO;进度条 MUST 实时更新

#### Scenario: 上传失败
- **WHEN** 文档格式不支持或文件损坏
- **THEN** 系统 MUST 显示明确错误(格式不支持 / 解析失败),不静默失败;audit log 记录失败

### Requirement: RAG 检索
系统 MUST 支持语义检索(query → top-K 相关文档片段) + 关键词检索 + 混合检索;Rerank + 引用溯源 V1.0+ 必含。

#### Scenario: 语义检索
- **WHEN** 用户 query "Q3 销售数据"
- **THEN** 系统 MUST:① embedding query ② Milvus 相似度检索 top-20 ③ Rerank 排序 ④ 返回 top-5 文档片段,每片段 MUST 含:文档名、页码/段落号、相似度分数、原文片段

#### Scenario: 引用溯源
- **WHEN** RAG 检索结果被 LLM 用于回答
- **THEN** 系统 MUST 在回答中标注引用源(文档名 + 段落号);点击引用 MUST 跳转原文对应位置

### Requirement: 文档版本管理
系统 MUST 支持文档的版本管理(每次重新上传/解析生成新版本,旧版本保留可查)。

#### Scenario: 重新上传同一文档
- **WHEN** 用户对已存在的文档重新上传
- **THEN** 系统 MUST 生成新版本(原文档保留为旧版本),新版本成为 active,旧版本可在历史中查询

### Requirement: 知识库权限
系统 MUST 支持知识库的访问控制(基于 RBAC 角色);用户的 RAG 检索 MUST 仅返回其有权访问的知识库内容。

#### Scenario: 权限隔离
- **WHEN** 用户 A(无权限)尝试 RAG 检索用户 B(财务)的知识库
- **THEN** 系统 MUST 阻断,返回空结果集,audit log 记录未授权访问尝试


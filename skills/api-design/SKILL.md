---
name: api-design
description: 设计符合 RESTful 规范的 API，输出 OpenAPI 3.0 规范文件。适用于接口设计或重构。
argument-hint: [API名称或资源]
allowed-tools: Read, Write
---
# API 设计技能

## 单一职责
产出无歧义的 API 契约。

## 核心输出
- **OpenAPI 3.0 YAML**：包含路径、请求/响应 Schema、错误格式。
- **分页/过滤/排序约定**：`page`、`size`、`sort` 查询参数语义。
- **错误响应标准**：统一 `code`、`message`、`details` 结构。

## 顶尖交付标准
- 接口评审后实际变更次数 ≤ 1 次。
- OpenAPI 文件可通过 Swagger Codegen 生成客户端 SDK 无错误。

## 实现要点
- 资源命名使用复数名词（`/users`、`/orders`）。
- 使用 `$ref` 复用 Schema 定义。
- 对每个接口提供至少一个请求/响应示例。
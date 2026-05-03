---
name: log-management
description: 部署结构化日志采集、索引与查询系统（Loki / ELK）。适用于集中式日志管理。
argument-hint: [服务名称]
allowed-tools: Read, Write, Bash
---
# 日志管理技能

## 单一职责
保障日志从产生到可查询的完整链路，不负责日志内容分析。

## 核心输出
- **OTLP 采集配置**：Promtail 或 OpenTelemetry Collector 配置，输出为 JSON 格式。
- **保留策略**：按时间（如 30 天）和体积自动清理，使用对象存储降低冷存储成本。
- **常用查询模板**：LogQL 或 Lucene 语法示例，覆盖错误追踪、慢请求定位。

## 顶尖交付标准
- 日志从写入到可查询延迟 ≤ 3 秒。
- 日志系统自身可用性 ≥ 99.9%，不因日志量激增而崩溃。

## 实现要点
- 强制日志格式：`{"timestamp":"...","level":"...","traceId":"...","message":"...","service":"..."}`
- 敏感字段（password、token）自动脱敏，通过 pipeline 阶段过滤。
- 为每个服务预设 Grafana 日志面板。
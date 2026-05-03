---
name: token-monitoring
description: 采集、聚合和预警 LLM Token 消耗，输出日报和超限告警。
argument-hint: [时间范围或智能体名称]
allowed-tools: Read, Write, Bash
---
# Token 监控技能

## 单一职责
追踪每一笔 LLM 调用的 Token 消耗，提供成本可见性。

## 核心输出
- **结构化日志**：每次调用生成一条 JSON 日志。
- **每日聚合报告**：按维度统计的 Token 量和成本。
- **实时预警**：预算超 80% 时主动告警。

## 顶尖交付标准
- 日志记录延迟 < 10ms（异步写入）。
- 日报生成时间 < 5 秒。

## 实现要点
- 在 LLM 调用封装层（如 `call_llm_with_logging` 函数）统一埋点。
- 使用 tiktoken 或模型 API 返回的精确 usage 字段。
- 成本计算基于各模型官方定价（如 Claude 3.5 Sonnet 输入 $3/MTok，输出 $15/MTok）。
---
name: monitoring-alerting
description: 部署 Prometheus + Grafana 监控体系，配置告警规则与仪表板。适用于保障服务可观测性。
argument-hint: [服务名称]
allowed-tools: Read, Write, Bash
---
# 监控告警技能

## 单一职责
让服务状态可量化、异常可感知。

## 核心输出
- **Prometheus 采集配置**：ServiceMonitor 或 PodMonitor 定义。
- **告警规则文件**：PromQL 表达式 + 抑制/分组规则。
- **Grafana 仪表板 JSON**：包含 RED 指标（Rate, Error, Duration）与业务指标。

## 顶尖交付标准
- 故障发生到告警通知 ≤ 1 分钟。
- 告警误报率 ≤ 5%（以周为统计周期）。

## 实现要点
- 使用 `prometheus-operator` 简化部署。
- 告警规则包含 `for` 持续时间避免瞬时抖动。
- 仪表板使用变量支持多环境切换。
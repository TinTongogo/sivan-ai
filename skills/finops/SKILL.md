---
name: finops
description: 预估云资源成本，跟踪实际支出，识别浪费并优化。
argument-hint: [服务或资源名称]
allowed-tools: Read, Write, Bash
---
# FinOps 成本管理技能

## 单一职责
让每一分云支出可追溯、可优化。

## 核心输出
- **成本预估报告**：基于 Terraform Plan 的资源清单计算月成本。
- **成本归因标签规范**：`team`、`project`、`environment`。
- **优化建议**：未使用资源、降配建议、Spot 实例机会。

## 顶尖交付标准
- 预估成本与实际支出偏差 ≤ 15%。
- 每月输出成本优化报告，节省 ≥ 5% 非必要支出。

## 实现要点
- 使用 Infracost 或 AWS Cost Explorer API。
- 强制所有资源打上成本标签。
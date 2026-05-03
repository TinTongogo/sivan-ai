---
name: data-quality
description: 定义并监控数据质量指标，防止垃圾数据污染模型。
argument-hint: [数据表或流]
allowed-tools: Read, Write, Bash
---
# 数据质量技能

## 单一职责
在数据进入模型前拦截异常。

## 核心输出
- **质量规则**：非空、唯一性、值域范围、分布漂移。
- **监控面板**：规则通过率、历史趋势。
- **告警与阻断**：质量低于阈值时停止训练。

## 顶尖交付标准
- 关键特征空值率 ≤ 1%。
- 分布漂移检测（PSI）超 0.2 时告警。

## 实现要点
- 使用 Great Expectations 或 Deequ。
- 与 Airflow 或 Dagster 集成。
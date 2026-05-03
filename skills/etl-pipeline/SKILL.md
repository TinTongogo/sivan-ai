---
name: etl-pipeline
description: 设计可维护、可扩展的数据提取转换加载流水线。
argument-hint: [数据源]
allowed-tools: Read, Write, Bash
---
# ETL 流水线技能

## 单一职责
可靠地将原始数据转化为分析就绪格式。

## 核心输出
- **流水线代码**：Spark、Flink 或 SQL。
- **调度配置**：Airflow DAG 或 Dagster Job。
- **数据血缘图**：字段级依赖关系。

## 顶尖交付标准
- 流水线失败率 ≤ 1%，失败后可自动重试。
- 数据延迟满足业务 SLA（如 T+1 或实时）。

## 实现要点
- 使用 dbt 管理 SQL 转换，DataHub 收集血缘。
- 增量处理避免全量扫描。
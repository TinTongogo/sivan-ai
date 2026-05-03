---
name: feature-store
description: 构建离线/在线统一的特征存储，保障训练服务一致性。
argument-hint: [特征域]
allowed-tools: Read, Write, Bash
---
# 特征存储技能

## 单一职责
让线上推理使用的特征与训练时完全一致。

## 核心输出
- **特征定义**：名称、类型、来源、新鲜度要求。
- **Feature Store 配置**：Feast、Hopsworks 或自研。
- **特征计算流水线**：批特征（Spark）、流特征（Flink）。

## 顶尖交付标准
- 训练-服务特征偏差 ≤ 0.5%。
- 在线特征获取延迟 ≤ 20ms（P99）。

## 实现要点
- 使用 Feast 作为开源特征存储。
- 特征数据同时写入离线存储（Parquet）和在线存储（Redis）。
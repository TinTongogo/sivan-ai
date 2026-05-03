---
name: vector-db
description: 部署和优化向量数据库，实现低延迟、高召回的大规模向量检索。适用于 RAG 系统知识库管理。
argument-hint: [应用场景]
allowed-tools: Read, Write, Bash
---
# 向量数据库技能

## 单一职责
提供稳定的向量存储与检索服务。

## 核心输出
- **部署配置**：Milvus / Qdrant 的 Helm Chart 或 docker-compose，含资源配额。
- **索引调优参数**：索引类型（HNSW/IVF）、`ef`、`M`、`nprobe`。
- **监控面板**：检索延迟、QPS、召回率、内存使用。

## 顶尖交付标准
- 百万级向量检索 P99 延迟 ≤ 50ms。
- 召回率（Recall@10）≥ 0.95。

## 实现要点
- 根据数据规模选择分片数量。
- 定期重建索引以优化查询性能。
- 启用持久化存储，防止数据丢失。
---
name: embedding-selection
description: 评估并选择最适合特定领域数据的 Embedding 模型。
argument-hint: [数据类型（文本/代码/多语言）]
allowed-tools: Read, Write, Bash
---
# Embedding 模型选型技能

## 单一职责
用数据证明哪个 Embedding 模型在你的任务上表现最好。

## 核心输出
- **候选模型列表**：BGE、E5、OpenAI、Voyage 等。
- **评估基准代码**：在自有测试集上计算检索 Recall。
- **选型报告**：性能、成本、延迟对比。

## 顶尖交付标准
- 选型结果在自有测试集上 Recall@5 提升 ≥ 10%（相比默认模型）。

## 实现要点
- 测试集必须与生产数据分布一致。
- 评估指标包含 MTEB 相关任务分数。
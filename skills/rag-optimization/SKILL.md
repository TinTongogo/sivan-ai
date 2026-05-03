---
name: rag-optimization
description: 提升检索增强生成的召回精度与答案忠实度，包括分块策略、混合检索与重排序。适用于知识密集型智能体。
argument-hint: [知识领域]
allowed-tools: Read, Write, Bash
---
# RAG 优化技能

## 单一职责
让检索到的片段与用户问题最相关。

## 核心输出
- **分块策略配置**：块大小、重叠量、语义分块规则。
- **混合检索 + 重排序代码**：BM25 + 向量，Cross-Encoder 重排。
- **Recall@K 评估报告**：不同 K 值下的命中率。

## 顶尖交付标准
- Recall@5 ≥ 0.90。
- 生成答案忠实度（Faithfulness）≥ 0.95。

## 实现要点
- 使用 BGE 或 E5 作为 Embedding 模型。
- 向量库索引选择 HNSW，参数 `efConstruction` 调高。
- 对检索结果进行上下文压缩，仅保留与问题最相关句子。
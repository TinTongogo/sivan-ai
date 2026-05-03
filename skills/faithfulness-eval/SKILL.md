---
name: faithfulness-eval
description: 评估 RAG 生成答案对检索片段的忠实程度。
argument-hint: [RAG 应用名称]
allowed-tools: Read, Write, Bash
---
# 忠实度评估技能

## 单一职责
量化答案中的幻觉比例。

## 核心输出
- **评估数据集**：问题、检索上下文、生成答案三元组。
- **评估脚本**：使用 LLM-as-judge 或 NLI 模型打分。
- **忠实度报告**：幻觉语句标注和改进建议。

## 顶尖交付标准
- 忠实度评分 ≥ 0.95。
- 可定位到幻觉的具体语句和缺失证据。

## 实现要点
- 使用 RAGAS 框架的 Faithfulness 指标。
- 或使用 NLI 模型（如 BART-large-MNLI）判断蕴含关系。
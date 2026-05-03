---
name: ab-testing
description: 设计并分析 A/B 实验，科学评估模型或功能效果。
argument-hint: [实验名称]
allowed-tools: Read, Write, Bash
---
# A/B 测试技能

## 单一职责
用统计方法证明新方案是否显著优于旧方案。

## 核心输出
- **实验设计**：假设、样本量计算、分流配置。
- **分析报告**：P 值、置信区间、效应量。
- **决策建议**：全量、继续实验、放弃。

## 顶尖交付标准
- 实验结论置信度 ≥ 95%。
- 实验期间无 SRM（样本比例不匹配）异常。

## 实现要点
- 使用 GrowthBook、LaunchDarkly 或自研分流。
- 分析时警惕多重比较问题（Bonferroni 校正）。
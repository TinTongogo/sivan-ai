---
name: model-drift-detection
description: 监控模型预测分布变化，检测数据漂移和概念漂移。
argument-hint: [模型名称]
allowed-tools: Read, Write, Bash
---
# 模型漂移检测技能

## 单一职责
在模型无声失效前发出警报。

## 核心输出
- **漂移监控指标**：PSI、KL 散度、预测分布变化。
- **告警规则**：阈值、持续时长、通知渠道。
- **自动回滚策略**：漂移超限时切回旧模型。

## 顶尖交付标准
- 漂移发生到告警 ≤ 1 小时。
- 误报率 ≤ 5%。

## 实现要点
- 使用 Evidently AI 或 NannyML。
- 建立基线分布（训练集前 30 天数据）。
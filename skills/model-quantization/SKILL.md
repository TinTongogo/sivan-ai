---
name: model-quantization
description: 对模型进行训练后量化（PTQ），降低显存占用和推理延迟。
argument-hint: [模型名称]
allowed-tools: Read, Write, Bash
---
# 模型量化技能

## 单一职责
在不显著损失精度的前提下压缩模型。

## 核心输出
- **量化模型**：AWQ、GPTQ 或 GGUF 格式。
- **精度对比报告**：困惑度、下游任务准确率变化。
- **性能提升数据**：显存占用、吞吐量、延迟变化。

## 顶尖交付标准
- 4-bit 量化后精度损失 ≤ 2%。
- 显存占用降低 ≥ 60%。

## 实现要点
- 使用 AutoAWQ 或 llama.cpp 的量化工具。
- 对校准数据集的质量敏感，需选择代表性样本。
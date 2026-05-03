---
name: hardware-acceleration
description: 利用 NPU、DSP、GPU 加速端侧推理，编写高性能算子。
argument-hint: [硬件平台]
allowed-tools: Read, Write, Bash
---
# 硬件加速技能

## 单一职责
榨干设备每一滴算力。

## 核心输出
- **算子优化代码**：Neon 汇编、Metal Shader、OpenCL Kernel。
- **框架适配层**：将模型转换为 Core ML、NNAPI 或 QNN 格式。
- **性能基准**：CPU 与加速器推理时间对比。

## 顶尖交付标准
- 使用硬件加速后推理速度提升 ≥ 2 倍，功耗降低 ≥ 30%。

## 实现要点
- Android 上优先使用 NNAPI 或 Qualcomm QNN。
- iOS 上使用 Core ML 和 ANE。
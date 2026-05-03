---
name: stream-processor
description: 构建实时音视频流处理管道，处理解码、推理、编码。
argument-hint: [应用类型]
allowed-tools: Read, Write, Bash
---
# 流媒体处理技能

## 单一职责
以最低延迟处理连续的音视频帧。

## 核心输出
- **GStreamer/FFmpeg Pipeline**：解码、缩放、推理、编码。
- **帧丢弃策略**：当推理跟不上时选择性丢非关键帧。
- **性能监控**：处理延迟、丢帧率、队列长度。

## 顶尖交付标准
- 端到端处理延迟 ≤ 200ms（不含网络传输）。
- 在 CPU 负载 80% 时仍能保持实时。

## 实现要点
- 使用硬件解码（VAAPI、NVDEC、VideoToolbox）。
- 推理与编解码异步流水线。
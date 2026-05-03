---
name: video-analytics
description: 对视频流进行实时分析（目标检测、行为识别、分割）。
argument-hint: [分析类型]
allowed-tools: Read, Write, Bash
---
# 视频分析技能

## 单一职责
从视频流中实时提取结构化信息。

## 核心输出
- **推理服务**：YOLO、ByteTrack、SlowFast 部署。
- **后处理逻辑**：NMS、目标跟踪、轨迹平滑。
- **输出 Schema**：检测框、类别、置信度、轨迹 ID。

## 顶尖交付标准
- 单帧推理 ≤ 30ms（GPU），支持 30fps 实时处理。
- 跟踪 ID 切换率 ≤ 5%。

## 实现要点
- 使用 TensorRT 或 ONNX Runtime 加速。
- 跳帧检测：每 N 帧做一次检测，中间帧用跟踪补全。
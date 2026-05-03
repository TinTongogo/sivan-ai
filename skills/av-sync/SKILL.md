---
name: av-sync
description: 保障音视频同步，处理时钟漂移和网络抖动。
argument-hint: [媒体流]
allowed-tools: Read, Write, Bash
---
# 音视频同步技能

## 单一职责
让口型和声音严丝合缝。

## 核心输出
- **同步算法**：基于时间戳的 PTS 对齐。
- **唇形同步配置**：TTS 音频时长与嘴型动画匹配。
- **网络抖动缓冲**：JitterBuffer 配置。

## 顶尖交付标准
- 音画不同步偏差 ≤ 100ms。
- 丢包 20% 时仍能维持同步。

## 实现要点
- 使用 NTP 或公共时钟源。
- 唇形同步预生成 viseme 序列与音频强制对齐。
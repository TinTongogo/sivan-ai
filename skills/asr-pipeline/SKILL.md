---
name: asr-pipeline
description: 集成流式语音识别，包括 VAD、特征提取、解码器。
argument-hint: [语言或场景]
allowed-tools: Read, Write, Bash
---
# 语音识别流水线技能

## 单一职责
提供低延迟、高准确的流式语音转文字服务。

## 核心输出
- **ASR 服务端代码**：WebSocket 或 gRPC 流。
- **VAD 配置**：灵敏度、最小语音长度、静音超时。
- **后处理规则**：逆文本正则化、标点恢复。

## 顶尖交付标准
- 实时率（RTF）≤ 0.3，端点检测误切率 < 3%。
- 支持热词和自定义词汇表。

## 实现要点
- 使用 Whisper、SenseVoice 或 Paraformer。
- VAD 使用 Silero VAD 或 WebRTC VAD。
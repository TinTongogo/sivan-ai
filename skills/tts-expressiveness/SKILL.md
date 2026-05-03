---
name: tts-expressiveness
description: 实现富有表现力的语音合成，支持情感、韵律控制。
argument-hint: [声音角色]
allowed-tools: Read, Write, Bash
---
# 表现力语音合成技能

## 单一职责
让合成语音传递情感和个性。

## 核心输出
- **TTS 模型部署配置**：VITS、GPT-SoVITS、CosyVoice。
- **情感控制接口**：快乐、悲伤、愤怒、惊讶等参数。
- **音色克隆脚本**：少量样本微调。

## 顶尖交付标准
- MOS 评分 ≥ 4.2（以真人 4.5 为基准）。
- 克隆音色相似度 ≥ 85%（说话人验证分数）。

## 实现要点
- 使用参考音频进行音色提示。
- 韵律标记（SSML）控制停顿、重音、语速。
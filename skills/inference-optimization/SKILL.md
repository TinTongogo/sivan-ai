---
name: inference-optimization
description: 降低 LLM 推理延迟与成本，包括量化部署、KV Cache 复用、Prompt Cache 策略。适用于生产环境部署。
argument-hint: [模型名称]
allowed-tools: Read, Write, Bash
---
# 推理优化技能

## 单一职责
优化推理引擎性能，不负责模型选型或微调。

## 核心输出
- **推理服务部署配置**：vLLM / TensorRT-LLM 启动参数，含量化级别。
- **Prompt Cache 命中率优化方案**：将系统提示与常用前缀固定化。
- **性能基准报告**：对比优化前后的 TTFT、吞吐量、成本。

## 顶尖交付标准
- 在输出质量无明显下降前提下，推理成本降低 ≥ 40%。
- P99 TTFT ≤ 200ms（首 token 延迟）。

## 实现要点
- 优先采用 AWQ 或 GPTQ 4-bit 量化。
- 对多轮对话场景启用自动 Prefix Caching。
- 监控 GPU 利用率和请求排队长度，动态调整并发。
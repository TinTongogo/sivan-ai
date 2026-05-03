---
name: llm-streaming
description: 实现大模型流式输出，包括 SSE 协议、中断处理、缓冲区管理。
argument-hint: [模型部署方式]
allowed-tools: Read, Write, Bash
---
# LLM 流式输出技能

## 单一职责
让用户感知到“即时响应”的体验。

## 核心输出
- **流式服务端代码**：FastAPI StreamingResponse 或 gRPC 流。
- **客户端消费逻辑**：EventSource 或 fetch + ReadableStream。
- **中断处理**：取消生成后立即释放 GPU 资源。

## 顶尖交付标准
- 首字延迟（TTFT）≤ 100ms（不含网络）。
- 中断请求后 GPU 显存占用在 1 秒内下降。

## 实现要点
- 使用 SSE 协议，Content-Type: text/event-stream。
- 客户端 AbortController 触发取消。
- 服务端检测客户端断开后停止生成。
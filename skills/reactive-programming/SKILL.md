---
name: reactive-programming
description: 使用 Spring WebFlux 和 Reactor 构建非阻塞、弹性数据流。适用于高并发 IO 密集型服务。
argument-hint: [组件或服务名称]
allowed-tools: Read, Write
---
# 响应式编程技能

## 单一职责
实现异步非阻塞的数据处理链。

## 核心输出
- **Mono/Flux 操作链代码**：含 `flatMap`、`zip`、错误恢复。
- **背压处理配置**：`onBackpressureBuffer` / `onBackpressureDrop`。
- **调度器切换建议**：阻塞任务用 `boundedElastic`。

## 顶尖交付标准
- 同等硬件下吞吐量提升 ≥ 2 倍，P99 延迟降低 ≥ 30%。

## 实现要点
- 禁止在响应式链中调用阻塞方法（如 `Thread.sleep`）。
- 使用 `StepVerifier` 进行单元测试。
- 数据库访问需使用 R2DBC 或异步驱动。
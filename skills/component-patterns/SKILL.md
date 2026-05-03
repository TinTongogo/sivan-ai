---
name: component-patterns
description: 设计可复用 UI 组件的接口、状态管理与复合模式。适用于构建组件库。
argument-hint: [组件名称或功能]
allowed-tools: Read, Write
---
# 组件设计模式技能

## 单一职责
定义组件的对外契约与内部状态边界。

## 核心输出
- **Props 类型定义**：TypeScript 精确类型，含可选/必填、回调签名。
- **复合组件 Context 结构**：如 `<Tabs>` 与 `<Tab>` 的共享状态。
- **受控/非受控模式切换示例**。

## 顶尖交付标准
- 组件在未预期场景下复用率 ≥ 70%。
- 无 props 钻取（prop drilling）现象，跨层级通信使用 Context 或组合。

## 实现要点
- 优先采用组合模式而非配置式巨型 props。
- 使用 `React.forwardRef` 支持 DOM 操作需求。
- 提供 Storybook 示例，展示所有变体。
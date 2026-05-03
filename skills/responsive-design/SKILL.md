---
name: responsive-design
description: 实现多端适配的响应式布局，包括移动优先、断点设计与图片适配。适用于跨设备界面开发。
argument-hint: [组件或页面名称]
allowed-tools: Read, Write
---
# 响应式设计技能

## 单一职责
确保 UI 在任何视口宽度下可用且美观。

## 核心输出
- **移动优先 CSS 代码**：Flex/Grid 基础布局，媒体查询增强。
- **断点定义**：基于内容而非设备，如 `sm: 640px`。
- **图片适配方案**：`srcset` + `sizes` 或 `<picture>` 元素。

## 顶尖交付标准
- 在 320px 至 2560px 宽度范围内无横向滚动条。
- 所有交互元素在移动端可点区域 ≥ 44×44px。

## 实现要点
- 使用相对单位 `rem`、`%`、`vw` 代替固定 `px`。
- 优先采用 Tailwind CSS 工具类实现响应式。
- 测试需覆盖真实移动设备（或 DevTools 模拟）。
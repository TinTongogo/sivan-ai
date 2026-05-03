---
name: ui-ux-design
description: 输出可量化的设计令牌与交互规范，使前端实现零歧义。
argument-hint: [页面或组件名称]
allowed-tools: Read, Write
---
# UI/UX 设计技能

## 单一职责
将设计意图转化为精确的、机器可读的设计变量和交互规则。

## 核心输出
- **设计令牌 JSON**：颜色、字体、间距、圆角、阴影。
- **交互状态矩阵**：默认、悬停、激活、禁用、加载、错误。
- **原型标注**：间距、尺寸、动画曲线。

## 顶尖交付标准
- 设计稿与最终实现视觉误差 ≤ 1px。
- 设计令牌可直接导入前端项目（CSS 变量或 Tailwind 配置）。

## 实现要点
- 使用 Figma Tokens 插件导出 JSON。
- 动画曲线使用标准 CSS `cubic-bezier` 值。
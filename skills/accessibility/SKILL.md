---
name: accessibility
description: 确保 Web 界面符合 WCAG 2.1 AA 标准，包括语义化 HTML、键盘导航、ARIA 属性、颜色对比度。适用于企业级应用。
argument-hint: [组件或页面名称]
allowed-tools: Read, Write
---
# 可访问性技能

## 单一职责
消除阻碍残障用户使用的技术障碍。

## 核心输出
- **组件级 a11y 检查清单**：聚焦、标签、对比度、ARIA 角色。
- **修复代码示例**：正确的语义结构、焦点管理。
- **测试报告**：Lighthouse 或 axe-core 扫描结果。

## 顶尖交付标准
- Lighthouse 可访问性评分 = 100。
- 所有交互元素支持键盘操作（Tab、Enter、Space）。

## 实现要点
- 使用 `<button>` 而非 `<div>` 模拟按钮。
- 自定义控件需实现相应 ARIA 属性（如 `role="slider"`）。
- 对比度至少 4.5:1（普通文本）。
---
name: inheritance-manager
description: 管理智能体间的临时能力继承，确保单向、无循环、单次有效。
argument-hint: [继承声明]
allowed-tools: Read
---
# 能力继承管理技能

## 单一职责
校验继承声明的合法性，并生成临时合并实例，不负责具体任务执行。

## 核心输出
- **继承解析器**：正则提取 `@target inherits from @source`。
- **循环依赖检测**：在解析阶段即拒绝 A 继承 B 且 B 继承 A。
- **临时实例生命周期**：任务执行完毕后立即销毁。

## 顶尖交付标准
- 嵌套继承（A inherits from B inherits from C）被直接拒绝，无运行时开销。
- 同名工具冲突时，以源智能体工具覆盖。

## 实现要点
- 在协调器层实现，不修改智能体定义文件。
- 仅继承 `tools` 和 `skills`，不继承模型、最大轮数等配置。
- 返回明确的成功或错误信息（含原因）。
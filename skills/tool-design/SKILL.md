---
name: tool-design
description: 设计智能体工具接口，包括 JSON Schema、参数校验、安全沙箱与错误处理。适用于扩展智能体能力。
argument-hint: [工具名称或功能]
allowed-tools: Read, Write
---
# 工具设计技能

## 单一职责
产出安全、健壮、易用的工具定义与实现。

## 核心输出
- **JSON Schema 定义**：含 `description`、`required`、类型约束。
- **工具实现代码**：含参数校验、超时控制、沙箱限制。
- **单元测试**：正常/异常/越权场景覆盖。

## 顶尖交付标准
- 工具被误用时返回明确错误信息，绝不泄露系统内部堆栈或路径。
- 所有文件操作限制在工作目录内，命令执行限制在白名单内。

## 实现要点
- 使用 Pydantic 或 Zod 进行输入校验。
- 超时默认 30 秒，可配置。
- 返回结果统一结构：`{"success": bool, "output": any, "error": str}`
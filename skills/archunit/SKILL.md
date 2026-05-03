---
name: archunit
description: 编写架构约束规则（Java ArchUnit），自动检查分层依赖、命名规范、注解使用。
argument-hint: [模块名称]
allowed-tools: Read, Write
---
# 架构约束自动化技能

## 单一职责
将架构决策转化为 CI 可执行的规则，防止腐化。

## 核心输出
- **ArchUnit 测试类**：验证层依赖方向、循环依赖、命名规范。
- **规则文档**：每条规则的业务含义和违规处理方式。

## 顶尖交付标准
- 所有架构约束 100% 自动化检查，无需人工 code review 依赖问题。
- 规则失败直接阻断 CI。

## 实现要点
- 核心规则：domain 层不依赖 infrastructure；controller 不调用 repository。
- 循环依赖检测使用 JDepend 或 ArchUnit 内置功能。
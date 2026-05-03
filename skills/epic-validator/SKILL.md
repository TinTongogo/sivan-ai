---
name: epic-validator
description: 检查 Epic 定义完整性，包括目标、范围、依赖、NFR 与验收标准。适用于 Epic 创建或评审阶段。
argument-hint: [Epic ID]
allowed-tools: Read
---
# Epic 验证技能

## 单一职责
审查 Epic 文档的要素完备性，不负责内容补全或拆分。

## 核心输出
- **缺失项清单**：目标、边界、用户角色、功能点、NFR、依赖关系。
- **可测试性评估**：验收标准是否可量化、可自动化。

## 顶尖交付标准
- 经验证通过的 Epic，后续用户故事拆分返工率 ≤ 10%。

## 实现要点
- 读取 `sprints/*/epics/*/requirements/epic-*.md` 内容。
- 按清单逐项核对，输出“✅/⚠️/❌”状态。
- 若缺失关键项，拒绝进入下一阶段。
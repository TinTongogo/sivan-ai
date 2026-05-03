---
name: contract-validator
description: 校验智能体产出是否符合消息契约 Schema，返回通过或失败详情。
argument-hint: [JSON文件路径]
allowed-tools: Read, Bash
---
# 契约校验技能

## 单一职责
验证文件内容是否符合预定义的 JSON Schema。

## 核心输出
- **校验结果**：`{ "valid": true/false, "errors": [...] }`
- **失败时**：不修改文件，仅报告错误。

## 顶尖交付标准
- 校验时间 ≤ 100ms。
- 错误信息精确到字段和原因。

## 实现要点
使用 Python 的 `jsonschema` 库执行校验。

### 使用方式
```bash
python scripts/validate_contract.py --schema .claude/contracts/agent-message.schema.json --instance .claude/results/task_001.json
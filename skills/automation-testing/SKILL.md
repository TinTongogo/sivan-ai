---
name: automation-testing
description: 编写和维护自动化测试脚本（API/UI），集成 CI/CD 实现回归检测。适用于提升测试效率。
argument-hint: [模块或API名称]
allowed-tools: Read, Write, Bash
---
# 自动化测试技能

## 单一职责
将测试用例转化为可重复执行的自动化脚本。

## 核心输出
- **API / UI 测试代码**：含数据工厂与清理逻辑。
- **测试报告生成器**：JUnit XML 或 Allure 报告。
- **CI 集成配置**：失败阻断规则与重试策略。

## 顶尖交付标准
- 测试误报率 ≤ 3%（非代码缺陷导致的失败）。
- 测试数据完全自包含，不依赖外部环境特定状态。

## 实现要点
- API 测试使用 RestAssured 或 Pytest + requests。
- UI 测试优先 Playwright，自带等待机制减少 flaky。
- 每个测试用例独立准备数据并清理。
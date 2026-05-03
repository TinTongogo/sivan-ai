---
name: cicd-pipeline
description: 设计从代码提交到生产的自动化流水线，包括构建、测试、扫描、多环境部署。适用于新建或改造部署流程。
argument-hint: [项目名称或仓库]
allowed-tools: Read, Write, Bash
---
# CI/CD 流水线技能

## 单一职责
定义可靠的自动化交付路径，不负责具体构建脚本内容。

## 核心输出
- **流水线配置文件**：GitHub Actions / GitLab CI YAML。
- **多环境部署参数化**：dev / staging / prod 通过变量区分。
- **安全扫描与测试门禁**：Trivy 镜像扫描 + 单元测试通过率要求。

## 顶尖交付标准
- 主干分支从 push 到部署至开发环境 ≤ 8 分钟。
- 生产部署必须经过人工审批。

## 实现要点
- 使用缓存加速依赖下载与构建。
- 测试失败立即阻断并通知提交者。
- 密钥管理使用平台 Secrets，日志不输出敏感信息。
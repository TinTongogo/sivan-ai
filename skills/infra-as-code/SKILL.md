---
name: infra-as-code
description: 使用 Terraform 管理云资源，实现声明式、版本化、幂等的基础设施。适用于云资源管理。
argument-hint: [资源类型或环境]
allowed-tools: Read, Write, Bash
---
# 基础设施即代码技能

## 单一职责
将云资源定义转化为可复用的 Terraform 模块，并管理远程状态。

## 核心输出
- **Terraform 模块**：VPC、ECS、RDS、OSS 等标准化组件。
- **远程状态锁配置**：S3 作为后端 + DynamoDB 实现状态锁。
- **变更计划预览**：`terraform plan` 输出人类可读的差异。

## 顶尖交付标准
- 一次 `apply` 成功率 ≥ 98%（排除配额、余额等外部因素）。
- 所有资源均定义 `tags`，用于成本归属。

## 实现要点
- 使用 `terraform-docs` 自动生成模块说明。
- 敏感变量通过环境变量或加密存储传入，禁止明文提交。
- 强制执行 `terraform fmt` 与 `validate` 检查。
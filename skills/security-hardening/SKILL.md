---
name: security-hardening
description: 消除 OWASP Top 10 常见漏洞，包括认证授权、输入校验、敏感数据加密。适用于后端安全防护。
argument-hint: [API或模块名称]
allowed-tools: Read, Write
---
# 安全加固技能

## 单一职责
在代码层面杜绝已知安全漏洞。

## 核心输出
- **认证授权配置**：Spring Security + JWT，密码 BCrypt 强度 12。
- **输入校验与输出编码规则**：`@Valid` 注解 + HTML 转义。
- **敏感数据加密与日志脱敏**：AES-256 加密，日志过滤器屏蔽关键字段。

## 顶尖交付标准
- 通过 OWASP ZAP 基线扫描，无高危漏洞。
- 所有 API 均需认证（除公开端点外）。

## 实现要点
- SQL 注入防护：JPA 参数化查询或 MyBatis `#{}`。
- 限流：使用 Bucket4j 实现用户级 QPS 限制。
- 配置安全响应头（CSP、HSTS、X-Frame-Options）。
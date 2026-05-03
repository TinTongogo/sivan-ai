---
name: threat-modeling
description: 使用 STRIDE 方法识别系统威胁，输出安全需求。
argument-hint: [系统或功能名称]
allowed-tools: Read, Write
---
# 威胁建模技能

## 单一职责
在设计阶段发现潜在安全问题，而非事后修补。

## 核心输出
- **数据流图**：信任边界、外部实体、数据存储。
- **威胁清单**：按 STRIDE 分类（欺骗、篡改、抵赖、信息泄露、拒绝服务、提权）。
- **缓解措施**：具体的安全控制。

## 顶尖交付标准
- 每个 Epic 涉及新数据流时必经威胁建模。
- 识别出的高危威胁在上线前已缓解。

## 实现要点
- 使用 OWASP Threat Dragon 或 Microsoft TMT。
- 重点审查认证、授权、数据验证环节。
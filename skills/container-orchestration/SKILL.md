---
name: container-orchestration
description: 定义 Kubernetes 工作负载的部署、服务暴露与发布策略。适用于容器化应用部署。
argument-hint: [应用名称]
allowed-tools: Read, Write, Bash
---
# 容器编排技能

## 单一职责
编写生产就绪的 K8s YAML 与发布规则。

## 核心输出
- **Deployment / Service / Ingress YAML**：含资源请求/限制、存活探针、就绪探针。
- **金丝雀发布配置**：Istio VirtualService 权重拆分或 Argo Rollouts 定义。
- **HPA 规则**：基于 CPU 或自定义指标的扩缩容策略。

## 顶尖交付标准
- 滚动更新期间 5xx 错误率 ≤ 0.1%。
- 探针配置确保 Pod 在真正就绪后才接收流量。

## 实现要点
- `maxSurge=1, maxUnavailable=0` 保证滚动更新零停机。
- 所有敏感配置通过 Secret 挂载，禁止环境变量明文传递。
- 使用 PodDisruptionBudget 保障自愿中断时的可用性。
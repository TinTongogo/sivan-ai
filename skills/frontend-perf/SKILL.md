---
name: frontend-perf
description: 量化并优化 Core Web Vitals，包括代码分割、资源预加载、图片适配。适用于提升首屏加载速度。
argument-hint: [页面或组件名称]
allowed-tools: Read, Write, Bash
---
# 前端性能优化技能

## 单一职责
提升 LCP、降低 CLS、改善 INP，不负责功能实现。

## 核心输出
- **Lighthouse 基线报告**：含瓶颈归因（渲染阻塞、大资源、布局偏移源）。
- **实施方案**：路由级代码分割、关键资源 preload、图片 WebP + srcset。
- **验证报告**：优化前后指标对比。

## 顶尖交付标准
- LCP ≤ 2.0 秒，CLS ≤ 0.05。
- 在 3G 网络模拟下 TTI ≤ 4 秒。

## 实现要点
- 使用 `webpack-bundle-analyzer` 定位大包。
- 对非首屏图片强制懒加载。
- 配置 CDN 缓存策略，静态资源设置 1 年有效期。
# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作提供指导。

## 项目概述

**Sivan** 是一个复杂的 AI 智能体团队管理系统，通过 69 个已定义技能协调 18 个专业智能体。系统使用 Orchestrator（乐团指挥）分解复杂任务并将其路由到适当的智能体，通过契约文件实现智能体间协作。内置 AgentResolver 动态编排引擎，支持 LLM 按需组建 squad 并自动解析/创建智能体。

## 系统架构

### 核心组件

1. **智能体** (`agents/`): 18 个具有明确定义角色、职责和约束的专业 AI 智能体
   - 每个智能体都有 Markdown 文件，包含：名称、显示名称、版本、核心职责、退出标准、反模式警示、可用技能、工具权限和禁止行为
   - 关键智能体：orchestrator（任务路由）、po（产品负责人）、architect（架构师）、be-dev（后端工程师）、fe-dev（前端工程师）、devops（运维工程师）、security-auditor（安全审计师）、qa（质量保证），以及各领域 AI 工程师

2. **技能** (`skills/{name}/SKILL.md`): 69 个模块化能力，智能体可以调用
   - 每个技能包含：名称、描述、参数提示、允许工具和实现细节
   - 按领域组织：软件工程、前端/移动端、AI/LLM、数据/MLOps、多媒体

3. **产品级路由系统**: 基于SQLite数据库的多策略智能路由系统，包含：
   - **语义路由器**: 中文分词 + 关键词匹配 + 同义词扩展
   - **ML路由器**: 基于scikit-learn的文本分类和意图识别
   - **上下文感知路由器**: 多维度上下文分析（任务复杂度、领域、用户专业水平等）
   - **自适应路由器**: 动态权重调整，基于历史表现优化路由策略
   - **集成路由器**: 统一管理所有路由策略，支持策略切换和综合分析
   - **SQLite数据库**: 持久化存储路由决策、候选得分、用户反馈和性能指标

4. **契约协作机制**: 基于SQLite数据库的智能体间协作系统
   - **数据库存储**: 4个核心表（contracts, contract_tags, contract_dependencies, contract_versions）
   - **版本控制**: 完整的版本历史跟踪，支持回滚和审计
   - **依赖管理**: 契约间依赖关系管理，确保协作一致性
   - **事件通知**: 基于观察者模式的事件发布/订阅机制
   - **契约类型**: global（全局）、api（接口）、ui（界面）、data（数据）、model（模型）
   - **状态管理**: draft（草稿）、reviewed（已审核）、approved（已批准）、deprecated（已废弃）

5. **Token成本监控**: 实时Token使用跟踪和成本管理系统
   - **使用记录**: 记录每次LLM调用的Token消耗和成本
   - **成本计算**: 支持多种模型定价（Claude、GPT系列等）
   - **预算管理**: 每日预算设置、使用监控、超限警报
   - **统计分析**: 按智能体、模型、时间维度统计分析
   - **MCP工具**: token_dashboard、token_daily_report、record_token_usage

6. **AgentResolver 动态编排引擎**: 智能体名称解析与自动创建
   - **3阶段语义匹配**: 精确匹配 → 归一化匹配 → IDF加权描述匹配（BFS传递缩写展开）
   - **创建防护**: 泛称特异性检查 + SRP职责重叠检查，宁缺毋滥
   - **技能继承**: 基于角色相似度自动匹配最相关技能（top-k 防超级单体）

7. **管理控制台**: 基于FastAPI的Web管理界面
   - **仪表板**: 系统状态概览、实时监控
   - **智能体管理**: 智能体列表查看、状态管理
   - **契约管理**: 契约浏览、搜索、状态更新
   - **Token统计**: Token使用分析、成本报告
   - **路由分析**: 路由决策统计、性能分析
   - **技能管理**: 69个技能同步、搜索和详情查看
   - **Squad管理**: Squad CRUD、执行编排、进度追踪
   - **周报管理**: 周报生成、查看、发布
   - **项目隔离**: 项目CRUD、知识库关联
   - **API接口**: 完整的RESTful API，支持数据导出

### 开发工作流

系统遵循 5 阶段实施路线图，**所有阶段已完成**：

1. **第一阶段**: 智能体 Prompt 定义（18 个智能体）✅ 已完成
2. **第二阶段**: 技能定义和维护人指定（69 项技能）✅ 已完成  
3. **第三阶段**: 产品级路由系统 + 契约协作机制实现 ✅ 已完成
   - ✅ 语义路由器（中文分词 + 关键词匹配 + 同义词扩展）
   - ✅ ML路由器（scikit-learn TF-IDF + 集成分类器 + 模型持久化）
   - ✅ 上下文感知路由器（8维度上下文分析 + 智能体画像）
   - ✅ 自适应路由器（动态权重调整 + 反馈学习）
   - ✅ SQLite数据库存储（6个表，完整分析功能）
   - ✅ 集成路由器（统一管理所有策略 + 策略切换）
   - ✅ MCP服务器集成（10个工具，完整路由分析）
4. **第四阶段**: 轻量监控 + 管理控制台基础功能 ✅ 已完成
   - ✅ 智能体间契约协作系统（SQLite数据库存储）
   - ✅ Token统计看板（成本监控和预算管理）
   - ✅ 完整协作流程测试验证
   - ✅ 管理控制台前端（FastAPI Web界面）
   - ✅ 技能管理模块（69个技能同步和管理）
   - ✅ 统一数据库架构（sivan.db整合所有数据）
5. **第五阶段**: Squad 可视化编排 + 效果评估周报 ✅ 已完成
   - ✅ Squad CRUD（创建、查询、更新、删除）
   - ✅ Squad执行引擎（多阶段编排 + 进度追踪）
   - ✅ 执行记录与详情查询
   - ✅ 周报生成与管理（基于Squad执行数据）
   - ✅ 管理控制台Squad/周报管理页面
   - ✅ 统一导航风格（所有页面使用侧边栏）

## 快速开始

### 1. 环境设置
```bash
# 安装依赖（使用 uv 进行 Python 包管理）
uv sync

# 首次运行会创建SQLite数据库和ML模型
uv run python server.py
```

### 2. 验证安装
服务器启动后应该显示：
```
✅ 系统初始化完成
📊 智能体数量: 18
📊 数据库文件: /path/to/data/sivan.db
📊 ML模型目录: /path/to/data/models/
🔧 可用MCP工具: 10
📁 契约数据库: contracts 表
🚀 路由系统: 集成路由器（自适应权重）
```

### 3. 基本使用
```bash
# 测试路由系统（DDD 架构）
uv run python -c "
from infrastructure.persistence.connection import SQLiteConnectionManager
from infrastructure.persistence.agent_repo import AgentRepository
from infrastructure.persistence.routing_repo import RoutingRepository
from domain.routing.service import RoutingService as DomainRoutingService
from application.services.routing_service import RoutingService

conn_mgr = SQLiteConnectionManager('data/sivan.db')
agent_repo = AgentRepository(conn_mgr)
routing_repo = RoutingRepository(conn_mgr)
domain_svc = DomainRoutingService()
routing_svc = RoutingService(domain_svc, routing_repo)

for name, agent in agent_repo.find_all_active().items():
    routing_svc.add_agent(name, agent.get_capabilities())

# 测试路由
result = routing_svc.route('设计用户登录API', {})
print(f'路由结果: {result}')

# 获取分析
analytics = routing_svc.get_analytics()
print(f'数据库决策数: {analytics.get(\"database\", {}).get(\"total_decisions\", 0)}')
"
```

### 4. 运行测试
```bash
# 运行测试套件
uv run python -m pytest tests/ -v
```

## 开发命令

### MCP 服务器开发
系统使用 FastMCP 进行 Model Context Protocol 集成。关键文件：
- `server.py`: 基于SLOID架构的MCP服务器，使用产品级路由系统
- 智能体作为 MCP 工具暴露给 Claude Desktop 集成
- 路由决策存储在SQLite数据库中，支持完整的分析和反馈学习

#### 启动服务器
```bash
# 直接运行（使用产品级路由系统）
uv run python server.py

# 服务器启动后会显示：
# - 智能体数量: 18
# - 数据库文件路径: data/sivan.db
# - ML模型目录: data/models/
# - 可用MCP工具: 10个
# - 路由系统状态: 集成路由器（自适应权重）
# - 路由策略: 语义、ML、上下文感知、自适应（4种策略）
```

### 测试套件
测试文件按类型组织在 `tests/` 目录：

```bash
# 运行所有测试
uv run python -m pytest tests/ -v

# 运行特定类型测试
uv run python -m pytest tests/unit/ -v           # 单元测试
uv run python -m pytest tests/functional/ -v     # 功能测试
uv run python -m pytest tests/integration/ -v    # 集成测试
uv run python -m pytest tests/performance/ -v    # 性能测试
uv run python -m pytest tests/e2e/ -v            # 端到端测试

# 运行单个测试文件
uv run python tests/unit/test_solid.py           # SLOID架构测试
uv run python tests/unit/test_sqlite_routing.py  # SQLite路由系统测试
uv run python tests/functional/test_server.py    # 服务器功能测试
uv run python tests/integration/test_mcp_integration.py  # MCP集成测试
uv run python tests/performance/test_performance.py      # 性能测试
uv run python tests/e2e/test_mcp.py              # 端到端测试
```

### 文档结构
文档按模块组织在 `docs/` 目录：
- `docs/architecture/` - 架构设计文档
- `docs/api/` - API接口文档
- `docs/usage/` - 使用指南文档
- `docs/development/` - 开发文档
- `docs/deployment/` - 部署文档

### 智能体开发工作流
1. **创建/修改智能体**: 按照模板结构编辑 `agents/{name}.md`
2. **定义技能**: 从现有技能目录中选择可用技能
3. **更新 Orchestrator 关键词**: 将智能体关键词添加到 Orchestrator 的路由表
4. **测试集成**: 验证智能体出现在 MCP 工具中并正确响应

## 关键模式和约束

### 智能体设计原则
- **单一职责**: 每个智能体有明确、专注的领域
- **退出标准**: 每个智能体都有必须在工作完成前满足的检查清单
- **反模式意识**: 每个智能体都记录要避免的行为
- **工具限制**: 智能体仅拥有其角色所需的权限（例如，orchestrator 不能写文件）

### Orchestrator 约束
- **不执行实际工作**: Orchestrator 只路由，从不执行实际工作
- **无状态**: 无跨会话记忆
- **无决策权**: 不确定时返回选项给用户选择
- **资源锁感知**: 识别共享资源并强制串行执行
- **失败透明**: 返回错误而不尝试修复

### 技能实现
- **单一职责**: 每项技能只做好一件事
- **工具限制**: 技能声明可以使用的工具
- **维护人指定**: 每项技能都有指定的维护智能体

## 文件结构约定

```
sivan/
├── domain/                  # 领域层（7 个有界上下文）
│   ├── agent/               entity, value_object, repository
│   ├── memory/              entity, value_object, repository
│   ├── contract/            entity, repository
│   ├── skill/               entity, repository
│   ├── routing/             entity, service, strategy
│   ├── task/                entity
│   └── knowledge_base/      entity, value_object, repository
├── infrastructure/          # 基础设施层
│   ├── persistence/         SQLAlchemy Core + 所有 Repository 实现
│   ├── agents/              base.py, generic_agent.py, orchestrator.py
│   ├── llm/                 Anthropic + OpenAI providers + factory
│   ├── memory/              forgetting_curve, session_memory, context_injector
│   ├── vector/              ChromaStore, KB ChromaStore
│   ├── rag/                 document_processor, embedding
│   └── logging/             setup, db_logger
├── application/services/    # 应用服务层
│   ├── agent_resolver.py    AgentResolver 动态编排引擎
│   ├── agent_service.py
│   ├── routing_service.py
│   ├── contract_service.py
│   ├── memory_service.py
│   ├── skill_service.py
│   ├── kb_service.py
│   ├── project_service.py
│   └── squad_matcher.py
├── interfaces/              # 接口层
│   ├── api/                 FastAPI 管理控制台
│   │   ├── admin.py         入口
│   │   ├── context.py       共享上下文
│   │   ├── routes/          14 个路由模块
│   │   └── services/        17 个服务模块
│   └── mcp/                 FastMCP 服务器（14 个工具）
├── templates/               16 个 Jinja2 模板
│   ├── base.html           基础模板（侧边栏导航）
│   ├── dashboard.html      仪表板
│   ├── chat.html           对话
│   ├── agents.html         智能体
│   ├── contracts.html      契约
│   ├── tokens.html         Token 统计
│   ├── routing.html        路由分析
│   ├── skills.html         技能
│   ├── squads.html         Squad
│   ├── reports.html        周报
│   ├── memory.html         记忆
│   ├── logs.html           日志
│   ├── knowledge_bases.html 知识库
│   ├── settings.html       设置
│   └── login.html          登录
├── agents/                  18 个智能体定义
├── skills/                  69 项技能（每项含 SKILL.md）
├── squads/                  预定义的智能体组合
├── config/                  settings.py
├── alembic/                 数据库迁移
├── scripts/                 种子数据与导入脚本
│   ├── seed_example_squads.py
│   ├── import_agents.py
│   └── import_skills.py
├── server.py                FastMCP 服务器入口
├── admin_console.py         FastAPI 管理控制台入口
├── pyproject.toml           Python 依赖
├── tests/                   测试套件
│   ├── unit/
│   ├── functional/
│   ├── integration/
│   ├── performance/
│   └── e2e/
└── data/
    ├── sivan.db             SQLite 统一数据库
    ├── chroma/              ChromaDB 持久化
    └── models/              ML 模型存储
```

## 常见开发任务

### 添加新智能体
1. 按照模板结构创建 `agents/{name}.md`
2. 从现有技能目录中定义可用技能
3. 设置适当的工具权限（默认限制性）
4. 将智能体关键词添加到 Orchestrator 的路由表
5. 测试智能体出现在 MCP 工具中

### 创建新技能
1. 创建 `skills/{技能名称}/SKILL.md`，包含：
   - 名称和描述
   - 使用参数提示
   - 允许工具（最小集）
   - 实现细节和质量标准
2. 指定维护智能体
3. 更新智能体定义以包含该技能
4. 测试技能调用

### 修改路由系统行为
- **路由策略配置**: 在 `server.py` 中配置使用的路由器类型
- **权重调整**: 自适应路由器根据历史表现自动调整策略权重
- **反馈学习**: 通过 `provide_routing_feedback` MCP工具提供反馈，优化路由
- **数据库查询**: 使用 `routing_analytics` MCP工具查看路由分析数据
- **策略切换**: 通过 `IntegratedRouter.switch_router()` 方法动态切换路由策略

## 测试和验证

### 测试分类
测试按类型组织在 `tests/` 目录：

1. **单元测试** (`tests/unit/`): 测试SLOID原则和设计模式
   - SLOID五大原则验证
   - 设计模式实现验证
   - 核心组件功能验证
   - **新增**: SQLite路由系统测试 (`test_sqlite_routing.py`)

2. **功能测试** (`tests/functional/`): 测试MCP服务器功能
   - 系统初始化测试
   - 智能体列表测试
   - 任务路由测试（使用产品级路由系统）
   - 契约管理测试
   - 路由分析功能测试

3. **集成测试** (`tests/integration/`): 测试MCP服务器集成
   - Claude Desktop模拟集成
   - MCP工具调用测试
   - 完整工作流程测试
   - 数据库持久化验证

4. **性能测试** (`tests/performance/`): 系统性能基准测试
   - 系统初始化性能
   - 路由性能测试（多策略对比）
   - 数据库查询性能
   - 并发性能测试
   - 内存使用测试

5. **端到端测试** (`tests/e2e/`): 完整工作流程测试
   - 完整MCP服务器流程
   - 智能体执行流程
   - 契约协作流程
   - 路由反馈学习流程

### 测试运行
```bash
# 运行所有测试
uv run python -m pytest tests/ -v

# 运行特定类型测试
uv run python -m pytest tests/unit/ -v
uv run python -m pytest tests/functional/ -v
uv run python -m pytest tests/integration/ -v
uv run python -m pytest tests/performance/ -v
uv run python -m pytest tests/e2e/ -v

# 运行单个测试文件
uv run python tests/unit/test_solid.py
```

### 智能体验证
每个智能体都有明确的"退出标准检查表"，必须满足：
- 领域特定的质量标准（例如，be-dev 需要 80% 测试覆盖率）
- 安全和性能要求
- 架构合规性检查

### MCP 集成测试
```bash
# 启动 MCP 服务器（使用产品级路由系统）
uv run python server.py

# 配置 Claude Desktop
# 在 Claude Desktop 中，验证工具出现并正确响应

# 测试路由功能:
# 1. 显式路由: @be-dev:设计用户认证API
# 2. 隐式路由: "实现登录功能" (使用语义+ML+上下文+自适应混合路由)
# 3. 路由分析: routing_analytics (查看SQLite数据库统计)
# 4. 智能体性能: agent_performance be-dev (查看历史表现)
# 5. 最近决策: recent_routing_decisions (查看最近路由记录)
# 6. 反馈学习: provide_routing_feedback 1 true (提供路由反馈)

# 关键MCP工具 (共14个):
# - list_agents: 列出所有可用智能体
# - call_agent: 调用特定智能体执行任务
# - orchestrator_route: 智能路由任务到最合适的智能体
# - create_contract: 创建智能体协作契约
# - list_contracts: 列出所有契约文件
# - contract_stats: 契约统计概览
# - system_status: 获取系统状态信息
# - routing_analytics: 查看路由分析数据
# - agent_performance: 查看智能体性能统计
# - recent_routing_decisions: 查看最近路由决策
# - provide_routing_feedback: 提供路由反馈以优化系统
# - search_knowledgebase: 语义搜索知识库
# - list_knowledgebases: 列出所有知识库
# - ingest_kb_document: 导入文档到知识库
```

### 管理控制台使用
```bash
# 1. 启动管理控制台
uv run python admin_console.py
# 或使用启动脚本
uv run python start_admin_console.py

# 2. 访问Web界面
# 打开浏览器访问: http://127.0.0.1:8001

# 3. 主要功能页面
# - 仪表板: / (系统概览和统计)
# - 智能体管理: /agents (查看和管理智能体)
# - 契约管理: /contracts (浏览和搜索契约)
# - Token统计: /tokens (Token使用分析和成本监控)
# - 路由分析: /routing (路由决策统计和性能分析)
# - 技能管理: /skills (69个技能搜索和详情查看)
# - Squad管理: /squads (Squad编排和执行)
# - 周报管理: /reports (周报生成和管理)

# 4. API接口
# - 系统统计: /api/stats
# - 智能体列表: /api/agents
# - 契约列表: /api/contracts
# - Token统计: /api/tokens
# - 路由统计: /api/routing
# - Token每日趋势: /api/token-daily
# - 技能管理: /api/skills, /api/skills/{id}, /api/skills-stats
# - Squad管理: /api/squads, /api/squads/{id}, /api/squads-stats, /api/squads-sync
# - Squad执行: /api/squads/{id}/execute
# - 执行记录: /api/squad-executions, /api/squad-executions/{id}
# - 周报管理: /api/weekly-reports, /api/weekly-reports/{id}
```

## 路由系统技术细节

### 1. SQLite数据库架构
系统使用SQLite数据库存储所有路由决策和相关数据，包含6个核心表：

```sql
-- 路由决策表 (核心表)
routing_decisions (id, task_description, selected_agent, routing_strategy, status, confidence_score, execution_time_ms, context_json, created_at)

-- 候选得分表 (记录所有候选智能体得分)
candidate_scores (id, decision_id, agent_name, score, rank, features_json)

-- 用户反馈表 (记录用户对路由决策的反馈)
user_feedback (id, decision_id, feedback_type, corrected_agent, feedback_text, rating, created_at)

-- 智能体性能表 (聚合性能指标)
agent_performance (agent_name, total_tasks, success_count, avg_confidence, avg_execution_time_ms, last_updated)

-- 策略性能表 (各路由策略性能跟踪)
strategy_performance (strategy_name, total_decisions, success_rate, avg_confidence, avg_execution_time_ms, feedback_correct_rate, weight)

-- 关键词特征表 (语义路由学习)
keyword_features (keyword, agent_name, occurrence_count, success_rate, last_used)
```

### 2. 路由策略实现

#### 语义路由器 (`semantic_router.py`)
- **中文分词**: 使用jieba进行中文文本分词
- **同义词扩展**: 内置同义词库，扩展匹配范围
- **特征权重**: 基于历史成功率动态调整关键词权重
- **意图分析**: 识别任务的技术、业务、UI等不同领域

#### ML路由器 (`ml_router.py`)
- **特征提取**: TF-IDF向量化，支持unigram和bigram
- **集成分类器**: 组合Naive Bayes、Logistic Regression、Random Forest
- **模型持久化**: 训练好的模型保存到文件，支持增量训练
- **自动重新训练**: 当新数据增长50%或超过7天时自动重新训练

#### 上下文感知路由器 (`context_router.py`)
- **8个上下文维度**: 任务复杂度、领域、用户专业水平、时间约束、协作需求、质量要求、安全要求、会话上下文
- **智能体画像**: 为每个智能体建立上下文偏好和成功率画像
- **实时学习**: 从每次路由决策中更新上下文知识

#### 自适应路由器 (`adaptive_router.py`)
- **动态权重**: 基于成功率(60%)、置信度(20%)、执行时间(10%)、反馈正确率(10%)计算权重
- **衰减因子**: 鼓励使用新策略，防止老策略垄断
- **后备策略**: 当所有策略失败时，使用最可靠策略或最常用智能体

#### 集成路由器 (`integrated_router.py`)
- **统一管理**: 管理所有路由策略，提供统一接口
- **策略切换**: 支持动态切换当前使用的路由策略
- **综合分析**: 获取所有策略的分析结果和共识智能体

### 3. 学习机制
- **反馈学习**: 用户可以通过MCP工具提供路由反馈
- **权重调整**: 自适应路由器根据反馈调整策略权重
- **特征更新**: 语义路由器根据纠正结果更新关键词特征
- **模型重训**: ML路由器在数据积累后自动重新训练

### 4. 分析功能
- **实时统计**: 路由成功率、平均执行时间、置信度分布
- **策略对比**: 各路由策略的性能对比分析
- **智能体分析**: 每个智能体的历史表现和趋势
- **时间序列**: 按时间维度的路由决策分析

## 重要注意事项

### 路由系统特性
- **产品级实现**: 所有路由策略均为生产就绪的实现
- **数据持久化**: 所有路由决策存储在SQLite数据库中
- **实时学习**: 从用户反馈中动态调整路由策略
- **多策略融合**: 4种路由策略协同工作，自适应选择最佳策略
- **完整监控**: 详细的性能分析和报告功能

### 技术栈
- **数据库**: SQLite (轻量级，无需额外服务)
- **ML框架**: scikit-learn (TF-IDF + 集成分类器)
- **中文处理**: jieba (中文分词)
- **MCP框架**: FastMCP (Model Context Protocol)
- **架构模式**: SLOID原则 + 设计模式

### 扩展性
- **新路由策略**: 实现 `IRouter` 接口即可添加新策略
- **数据库扩展**: SQLite表结构设计支持扩展新功能
- **智能体扩展**: 通过工厂模式添加新智能体类型
- **技能扩展**: 模块化技能设计，支持动态添加

### 性能考虑
- **数据库索引**: 关键字段已建立索引，优化查询性能
- **模型缓存**: ML模型持久化存储到 `data/models/` 目录，避免重复训练
- **内存管理**: 历史数据限制，防止内存泄漏
- **并发安全**: SQLite连接管理，支持并发访问
- **模型目录**: 自动创建的 `data/models/` 目录存储训练好的ML模型文件

系统设计具有高度可扩展性：可以添加新的智能体、技能和路由策略，而无需修改核心架构，遵循已建立的SLOID原则和设计模式。
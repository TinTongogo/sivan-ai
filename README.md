# Sivan - AI 智能体团队管理系统

![Python Version](https://img.shields.io/badge/python-3.13%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Architecture](https://img.shields.io/badge/architecture-SLOID-orange)
![Status](https://img.shields.io/badge/status-production%20ready-brightgreen)

**Sivan** 是一个基于 SLOID 架构和设计模式构建的复杂 AI 智能体团队管理系统。系统通过 69 个已定义技能协调 18 个专业智能体，使用产品级路由系统将复杂任务智能路由到适当的智能体，并通过契约文件实现智能体间协作。内置 AgentResolver 动态编排引擎，支持 LLM 按需组建 squad 并自动解析/创建智能体。

## ✨ 核心特性

### 🏗️ **SLOID 架构**
- **S**ingle Responsibility (单一职责) - 每个智能体专注单一领域
- **L**iskov Substitution (里氏替换) - 智能体可无缝替换
- **O**pen/Closed (开闭原则) - 扩展无需修改现有代码
- **I**nterface Segregation (接口隔离) - 清晰定义的接口边界
- **D**ependency Inversion (依赖倒置) - 高层模块不依赖低层细节

### 🤖 **智能体生态系统**
- **18 个专业智能体**：架构师、后端工程师、前端工程师、DevOps、安全审计师等
- **69 项模块化技能**：按领域组织（软件工程、AI/LLM、数据/MLOps、多媒体）
- **契约协作机制**：智能体通过契约文件进行通信和协调

### 🚀 **产品级路由系统**
- **语义路由器**：中文分词 + 关键词匹配 + 同义词扩展
- **ML 路由器**：scikit-learn TF-IDF + 集成分类器
- **上下文感知路由器**：8维度上下文分析
- **自适应路由器**：动态权重调整，基于历史表现优化
- **SQLite 数据库**：完整的数据持久化和分析功能

### 🔌 **MCP 集成**
- **FastMCP 3.x**：与 Claude Desktop 无缝集成
- **实时路由分析**：查看路由决策、智能体性能、策略对比
- **反馈学习**：用户反馈驱动路由系统持续优化

## 📋 系统架构

### 核心组件

```
sivan/
├── domain/                # 领域层（7 个有界上下文）
│   ├── agent/             entity, value_object, repository interfaces
│   ├── memory/            entity, value_object, repository interfaces
│   ├── contract/          entity, repository interfaces
│   ├── routing/           entity, service, strategy
│   └── ...                skill, task, knowledge_base
├── infrastructure/        # 基础设施层
│   ├── persistence/       SQLAlchemy Core + Repositories
│   ├── agents/            base.py, generic_agent.py, orchestrator.py
│   ├── llm/               Anthropic + OpenAI providers
│   ├── memory/            遗忘曲线 + 上下文注入
│   ├── vector/            ChromaDB 向量存储
│   ├── rag/               文档处理 + 嵌入
│   └── logging/           loguru + DB 日志
├── application/services/  # 应用服务层
│   ├── agent_resolver.py  AgentResolver 动态编排
│   ├── agent_service.py
│   ├── routing_service.py
│   ├── contract_service.py
│   ├── memory_service.py
│   ├── skill_service.py
│   ├── kb_service.py
│   ├── project_service.py
│   └── squad_matcher.py
├── interfaces/            # 接口层
│   ├── api/               FastAPI 管理控制台（14 个路由模块）
│   └── mcp/               FastMCP 服务器（14 个工具）
├── templates/             16 个 Jinja2 模板
├── agents/                18 个智能体定义
├── skills/                69 项技能定义
├── config/                settings.py
├── alembic/               数据库迁移
├── scripts/               种子数据与导入脚本
└── data/
    ├── sivan.db           SQLite 统一数据库
    ├── chroma/            ChromaDB 持久化
    └── models/            ML 模型存储
```

### 技术栈

- **Python 3.13+**：核心编程语言
- **FastMCP**：Model Context Protocol 框架
- **SQLite**：轻量级数据库存储
- **scikit-learn**：机器学习路由
- **jieba**：中文文本分词
- **pytest**：测试框架

## 🚀 快速开始

### 1. 环境设置

```bash
# 克隆仓库
git clone <repository-url>
cd sivan

# 安装依赖 (使用 uv 进行 Python 包管理)
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
🔧 可用工具: 14
📁 契约数据库: 4 个核心表（版本历史 + 依赖管理）
🌐 管理控制台: http://127.0.0.1:8001
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

result = routing_svc.route('设计用户登录API', {})
print(f'路由结果: {result}')

analytics = routing_svc.get_analytics()
print(f'数据库决策数: {analytics.get(\"database\", {}).get(\"total_decisions\", 0)}')
"
```

### 4. 运行测试

```bash
# 运行测试套件
uv run python -m pytest tests/ -v
```

## 🔧 MCP 服务器集成

### 启动服务器

```bash
# 直接运行（使用产品级路由系统）
uv run python server.py
```

### 配置 Claude Desktop

1. 启动 Sivan MCP 服务器
2. 在 Claude Desktop 中添加 MCP 服务器：
   - 协议：`stdio`
   - 命令：`uv run python /path/to/sivan/server.py`
3. 验证工具出现并正确响应

### 可用 MCP 工具（共 14 个）

| 工具名称 | 描述 |
|---------|------|
| `list_agents` | 列出所有可用智能体 |
| `call_agent` | 调用特定智能体执行任务 |
| `orchestrator_route` | 智能路由任务到最合适的智能体 |
| `create_contract` | 创建智能体协作契约 |
| `list_contracts` | 列出所有契约（支持状态/类型筛选） |
| `contract_stats` | 契约统计概览 |
| `system_status` | 获取系统状态信息 |
| `routing_analytics` | 查看路由分析数据 |
| `agent_performance` | 查看智能体性能统计 |
| `recent_routing_decisions` | 查看最近路由决策 |
| `provide_routing_feedback` | 提供路由反馈以优化系统 |
| `search_knowledgebase` | 语义搜索知识库 |
| `list_knowledgebases` | 列出所有知识库 |
| `ingest_kb_document` | 导入文档到知识库 |

## 📊 路由系统技术细节

### SQLite 数据库架构

系统使用 SQLite 数据库存储所有路由决策和相关数据，包含 6 个核心表：

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

### 路由策略实现

#### 1. 语义路由器 (`semantic_router.py`)
- **中文分词**：使用 jieba 进行中文文本分词
- **同义词扩展**：内置同义词库，扩展匹配范围
- **特征权重**：基于历史成功率动态调整关键词权重
- **意图分析**：识别任务的技术、业务、UI 等不同领域

#### 2. ML 路由器 (`ml_router.py`)
- **特征提取**：TF-IDF 向量化，支持 unigram 和 bigram
- **集成分类器**：组合 Naive Bayes、Logistic Regression、Random Forest
- **模型持久化**：训练好的模型保存到文件，支持增量训练
- **自动重新训练**：当新数据增长 50% 或超过 7 天时自动重新训练

#### 3. 上下文感知路由器 (`context_router.py`)
- **8个上下文维度**：任务复杂度、领域、用户专业水平、时间约束、协作需求、质量要求、安全要求、会话上下文
- **智能体画像**：为每个智能体建立上下文偏好和成功率画像
- **实时学习**：从每次路由决策中更新上下文知识

#### 4. 自适应路由器 (`adaptive_router.py`)
- **动态权重**：基于成功率(60%)、置信度(20%)、执行时间(10%)、反馈正确率(10%)计算权重
- **衰减因子**：鼓励使用新策略，防止老策略垄断
- **后备策略**：当所有策略失败时，使用最可靠策略或最常用智能体

#### 5. 集成路由器 (`integrated_router.py`)
- **统一管理**：管理所有路由策略，提供统一接口
- **策略切换**：支持动态切换当前使用的路由策略
- **综合分析**：获取所有策略的分析结果和共识智能体

### 学习机制

- **反馈学习**：用户可以通过 MCP 工具提供路由反馈
- **权重调整**：自适应路由器根据反馈调整策略权重
- **特征更新**：语义路由器根据纠正结果更新关键词特征
- **模型重训**：ML 路由器在数据积累后自动重新训练

### 分析功能

- **实时统计**：路由成功率、平均执行时间、置信度分布
- **策略对比**：各路由策略的性能对比分析
- **智能体分析**：每个智能体的历史表现和趋势
- **时间序列**：按时间维度的路由决策分析

## 🧪 测试套件

### 测试分类

```bash
# 运行所有测试
uv run python -m pytest tests/ -v

# 运行特定类型测试
uv run python -m pytest tests/unit/ -v           # 单元测试
uv run python -m pytest tests/functional/ -v     # 功能测试
uv run python -m pytest tests/integration/ -v    # 集成测试
uv run python -m pytest tests/performance/ -v    # 性能测试
uv run python -m pytest tests/e2e/ -v            # 端到端测试
```

### 测试文件说明

| 测试文件 | 描述 | 关键测试点 |
|---------|------|-----------|
| `tests/unit/test_solid.py` | SLOID 架构测试 | 验证五大原则和设计模式 |
| `tests/unit/test_sqlite_routing.py` | SQLite 路由系统测试 | 数据库操作和路由策略 |
| `tests/functional/test_server.py` | 服务器功能测试 | MCP 工具和系统初始化 |
| `tests/integration/test_mcp_integration.py` | MCP 集成测试 | Claude Desktop 集成 |
| `tests/performance/test_performance.py` | 性能测试 | 系统性能和并发处理 |
| `tests/e2e/test_mcp.py` | 端到端测试 | 完整工作流程验证 |

## 📈 开发路线图

### ✅ 已完成阶段（v1.0）

1. **第一阶段**：智能体 Prompt 定义（18 个智能体）
2. **第二阶段**：技能定义和维护人指定（69 项技能）
3. **第三阶段**：产品级路由系统 + 契约协作机制
   - ✅ 语义路由器（中文分词 + 关键词匹配 + 词边界修正）
   - ✅ ML 路由器（scikit-learn + TF-IDF + 集成分类器）
   - ✅ 上下文感知路由器（8维度上下文分析）
   - ✅ 自适应路由器（动态权重调整）
   - ✅ SQLite 数据库存储（6个表，完整分析功能）
   - ✅ 集成路由器（统一管理所有策略）
4. **第四阶段**：管理控制台 + Token 监控 ✅
   - ✅ FastAPI Web 界面（16 个模板页面）
   - ✅ Token 使用跟踪 + 预算管理
   - ✅ DDD 四层架构重构
   - ✅ RAG 知识库 + ChromaDB
   - ✅ 记忆管理系统 + 遗忘曲线
5. **第五阶段**：Squad 编排 + 周报 ✅
   - ✅ Squad CRUD + 5 种编排模式
   - ✅ HITL 逐阶段执行 + 契约传播
   - ✅ 周报自动生成/发布/下载
   - ✅ WebSocket 实时对话 + 日志
6. **第六阶段**：AgentResolver 动态编排 ✅
   - ✅ 3阶段语义匹配（精确 → 归一化 → IDF加权描述）
   - ✅ 创建防护（泛称检查 + SRP 职责重叠检查）
   - ✅ 技能继承（基于角色相似度自动匹配技能）
   - ✅ 全链路缓存同步（orchestrator single 路径 + global cache reload）

### 🔮 未来规划（v1.1+）

- 项目隔离（多租户数据隔离）
- MCP 多 Key 管理与审计
- 多模态 RAG（Qwen3-VL）
- Agent 技能使用分析和优化建议
- 三层评估系统（任务/Agent/技能评分）

## 🖥️ 管理控制台

```bash
# 启动 Web 管理界面
uv run python admin_console.py
# 访问 http://127.0.0.1:8001
```

提供 16 个功能页面：仪表板、项目、智能体、契约、Token 统计、路由分析、技能、Squad、周报、对话、知识库、记忆、日志、设置、登录。完整 RESTful API 支持数据导出。

## 🛠️ 开发指南

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

- **路由策略配置**：在 `server.py` 中配置使用的路由器类型
- **权重调整**：自适应路由器根据历史表现自动调整策略权重
- **反馈学习**：通过 `provide_routing_feedback` MCP 工具提供反馈，优化路由
- **数据库查询**：使用 `routing_analytics` MCP 工具查看路由分析数据
- **策略切换**：通过 `IntegratedRouter.switch_router()` 方法动态切换路由策略

## 📚 设计原则

### 智能体设计原则

- **单一职责**：每个智能体有明确、专注的领域
- **退出标准**：每个智能体都有必须在工作完成前满足的检查清单
- **反模式意识**：每个智能体都记录要避免的行为
- **工具限制**：智能体仅拥有其角色所需的权限

### Orchestrator 约束

- **不执行实际工作**：Orchestrator 只路由，从不执行实际工作
- **无状态**：无跨会话记忆
- **无决策权**：不确定时返回选项给用户选择
- **资源锁感知**：识别共享资源并强制串行执行
- **失败透明**：返回错误而不尝试修复

### 技能实现

- **单一职责**：每项技能只做好一件事
- **工具限制**：技能声明可以使用的工具
- **维护人指定**：每项技能都有指定的维护智能体

## 🔍 性能考虑

- **数据库索引**：关键字段已建立索引，优化查询性能
- **模型缓存**：ML 模型持久化存储，避免重复训练
- **内存管理**：历史数据限制，防止内存泄漏
- **并发安全**：SQLite 连接管理，支持并发访问

## 🚀 扩展性

- **新路由策略**：实现 `IRouter` 接口即可添加新策略
- **数据库扩展**：SQLite 表结构设计支持扩展新功能
- **智能体扩展**：通过工厂模式添加新智能体类型
- **技能扩展**：模块化技能设计，支持动态添加

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 📞 支持

如有问题或建议，请：
1. 查看 [文档](docs/)
2. 提交 [Issue](https://github.com/yourusername/sivan/issues)
3. 加入讨论

---

**Sivan** - 让 AI 智能体团队协作更智能、更高效！
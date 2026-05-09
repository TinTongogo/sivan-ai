# Sivan 项目 DDD 重构 + 记忆管理系统 实施计划

## Context

Sivan 是一个 AI 智能体团队管理系统，现有代码组织为扁平 `core/` 目录（~5000 行），缺少分层架构。本次重构目标是：

1. **DDD 分层**：按 domain / infrastructure / application / interfaces 组织代码
2. **记忆管理系统**：新增 4 级分层记忆 + 遗忘曲线 + 向量检索
3. **设计模式应用**：Repository、Strategy、Factory、Observer 等
4. **渐进迁移**：旧代码保持可用，边迁移边验证

---

## 新目录结构

```
sivan/
├── domain/                    # 领域层 - 实体、值对象、仓库接口、领域服务
│   ├── __init__.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── entity.py          # Agent, AgentConfig 实体
│   │   ├── value_object.py    # Capability, SkillRef, ToolPermission
│   │   └── repository.py      # IAgentRepository 接口
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── entity.py          # MemoryEntry, MemoryLevel enum
│   │   ├── value_object.py    # MemoryQuery, MemoryStats
│   │   └── repository.py      # IMemoryRepository 接口
│   ├── contract/
│   │   ├── __init__.py
│   │   ├── entity.py          # Contract, ContractVersion
│   │   ├── value_object.py    # ContractType, ContractStatus
│   │   └── repository.py      # IContractRepository 接口
│   ├── skill/
│   │   ├── __init__.py
│   │   ├── entity.py          # Skill 实体
│   │   └── repository.py      # ISkillRepository 接口
│   ├── routing/
│   │   ├── __init__.py
│   │   ├── entity.py          # RoutingDecision, CandidateScore
│   │   ├── service.py         # RoutingService (聚合所有策略)
│   │   └── strategy.py        # IRoutingStrategy 接口 (原 IRouter)
│   ├── task/
│   │   ├── __init__.py
│   │   ├── entity.py          # Task, TaskResult
│   │   └── service.py         # TaskService
│   └── common/
│       ├── __init__.py
│       ├── interfaces.py      # 跨领域通用接口 (IEventPublisher, ILogger)
│       ├── value_object.py    # 通用值对象 (TimeRange, PageRequest)
│       └── exceptions.py      # 领域异常
│
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── connection.py      # 统一 SQLite 连接管理 (单例连接池)
│   │   ├── agent_repo.py      # AgentRepository (SQLite)
│   │   ├── memory_repo.py     # MemoryRepository (SQLite)
│   │   ├── contract_repo.py   # ContractRepository (SQLite)
│   │   ├── skill_repo.py      # SkillRepository (SQLite)
│   │   ├── routing_repo.py    # RoutingRepository (SQLite)
│   │   ├── token_repo.py      # TokenUsageRepository (SQLite)
│   │   └── migrations.py      # 数据库迁移版本管理
│   ├── vector/
│   │   ├── __init__.py
│   │   └── chroma_store.py    # ChromaDB 向量存储封装 (持久化 + 语义检索)
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── forgetting_curve.py # 遗忘曲线计算 (Ebbinghaus)
│   │   ├── session_memory.py  # 会话级记忆 (内存中，短期)
│   │   └── context_injector.py # 记忆注入到 Agent 上下文的逻辑
│   └── cache/
│       ├── __init__.py
│       └── memory_cache.py    # 近期记忆 LRU 缓存
│
├── application/
│   ├── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── agent_service.py       # 智能体应用服务
│   │   ├── routing_service.py     # 路由应用服务
│   │   ├── contract_service.py    # 契约应用服务
│   │   ├── memory_service.py      # 记忆应用服务 (读/写/检索)
│   │   ├── skill_service.py       # 技能应用服务
│   │   └── token_service.py       # Token 统计应用服务
│   └── dto/
│       ├── __init__.py
│       └── memory_dto.py     # 记忆相关数据传输对象
│
├── interfaces/
│   ├── __init__.py
│   ├── api/                   # FastAPI 路由 (从 admin_console.py 拆分)
│   │   ├── __init__.py
│   │   ├── app.py             # FastAPI 应用工厂
│   │   ├── middleware.py      # 认证中间件 (现有)
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── agents.py
│   │   │   ├── contracts.py
│   │   │   ├── skills.py
│   │   │   ├── routing.py
│   │   │   ├── tokens.py
│   │   │   ├── squads.py
│   │   │   ├── reports.py
│   │   │   ├── memory.py      # 记忆管理 API (新)
│   │   │   └── dashboard.py
│   │   └── admin.py           # admin_console.py 精简版 (调用拆分后的路由)
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py          # MCP 服务器 (从 server.py 迁移)
│   │   └── tools.py           # MCP 工具定义 (list_agents, call_agent 等)
│   └── web/
│       ├── __init__.py
│       └── templates/         # Jinja2 模板 (保持现有)
│
├── core/                      # 保留旧代码，仅做适配
│   ├── __init__.py
│   ├── old_adapters.py        # 适配器：将旧接口映射到新接口
│   └── ... (现有文件不变)
│
├── config/
│   ├── __init__.py
│   └── settings.py            # 配置管理 (环境变量读取)
│
├── tests/
│   ├── __init__.py
│   ├── domain/
│   │   └── memory/
│   │       └── test_forgetting_curve.py
│   ├── infrastructure/
│   │   └── vector/
│   │       └── test_sqlite_vector.py
│   └── application/
│       └── test_memory_service.py
│
├── server.py                  # 兼容入口：from interfaces.mcp.server import app
├── admin_console.py           # 兼容入口：from interfaces.api.admin import console_app
├── main.py                    # 启动入口
├── data/                      # 数据目录 (不变)
└── pyproject.toml             # 依赖 (不变)
```

---

## 记忆管理系统设计

### 4 级记忆层次

| 层级 | 标识符 | 持久化 | 衰减周期 | 用途 |
|---|---|---|---|---|
| Session | `session:<id>` | 内存 (dict) | 1 小时 | 当前对话上下文，短期记忆 |
| User | `user:<id>` | SQLite | 24 小时 | 用户偏好、历史交互模式 |
| Team | `team:<id>` | SQLite + 向量 | 7 天 | 团队协作模式、分工知识 |
| Project | `project:<id>` | SQLite + 向量 | 30 天 | 全局配置、系统级知识 |

### 遗忘曲线 (Ebbinghaus)

```
R = e^(-t / S)
```

- R = retention rate (0~1)
- t = time elapsed since last access (hours)
- S = memory strength in hours
  - Session: S = 1 (1 小时后剩 37%)
  - User: S = 24 (1 天后剩 37%)
  - Team: S = 168 (7 天后剩 37%)
  - Project: S = 720 (30 天后剩 37%)

**更新策略：** 每次访问记忆条目时，重置 t = 0 (retrieval strengthens memory)

**归档阈值：** 当 R < 0.1 时，记忆进入"低频"状态，可被压缩摘要

### 向量存储设计 (ChromaDB)

使用 **ChromaDB**（开源轻量向量数据库）替代自定义 SQLite BLOB 方案：

- **存储引擎**: ChromaDB 内置持久化 (基于 SQLite + Parquet)
- **Embedding 模型**: 默认 `all-MiniLM-L6-v2` (384 维，通过 sentence-transformers)，自动处理文本→向量转换
- **相似度算法**: 默认余弦距离 (cosine distance)，内置 HNSW 索引加速
- **元数据过滤**: Chroma 原生支持 `where` 条件过滤 (level, scope_id 等)
- **持久化路径**: `data/chroma/` 目录，自动管理

**ChromaStore 封装：**
```python
import chromadb

class ChromaStore:
    """ChromaDB 向量存储封装，提供记忆专用接口。"""

    def __init__(self, persist_dir: str = "data/chroma"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name="sivan_memories",
            metadata={"hnsw:space": "cosine"},  # HNSW 索引加速
        )

    def store(self, memory_id: str, text: str, level: str, scope_id: str,
              metadata: dict | None = None) -> None:
        """存储记忆文本及元数据。Chroma 自动生成 embedding。"""
        self.collection.add(
            ids=[memory_id],
            documents=[text],
            metadatas=[{"level": level, "scope_id": scope_id, **(metadata or {})}],
        )

    def search(self, query: str, level: str | None = None,
               scope_id: str | None = None, top_k: int = 10):
        """语义搜索，支持 level/scope 过滤。"""
        where_filters = {}
        if level:
            where_filters["level"] = level
        if scope_id:
            where_filters["scope_id"] = scope_id
        return self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filters or None,
        )

    def delete(self, memory_id: str) -> None:
        self.collection.delete(ids=[memory_id])
```

**优势：**
- 无需手动管理 embedding 生成、向量序列化、相似度计算
- 内置 HNSW 索引，10 万级向量亚秒级检索
- 生产可用，支持客户端/服务端模式
- pip install chromadb 即可使用

### 上下文注入逻辑

当 Agent 执行任务时，系统自动：
1. 从记忆库检索相关记忆 (基于当前 user + team 上下文)
2. 按相关性排序，取 top-K
3. 保留率 R > 0.3 的记忆才注入
4. 注入到 Agent 的 system_prompt 附加段

---

## 设计模式应用

| 模式 | 用途 | 位置 |
|---|---|---|
| **Repository** | 数据访问抽象，domain 定义接口，infrastructure 实现 | `domain/*/repository.py` + `infrastructure/persistence/*_repo.py` |
| **Strategy** | 路由策略可替换 | `domain/routing/strategy.py` + 具体策略类 |
| **Factory** | 复杂对象创建 | `domain/agent/entity.py` AgentFactory |
| **Observer** | 契约事件通知 | `domain/common/interfaces.py` IEventPublisher |
| **Template Method** | Agent 执行流程骨架 | `domain/agent/entity.py` BaseAgent |
| **Adapter** | 旧 core/ 代码适配新接口 | `core/old_adapters.py` |
| **Singleton** | 数据库连接、系统单例 | `infrastructure/persistence/connection.py` |

---

## 实施阶段 (按顺序)

### Phase 1: 新目录骨架 + 记忆系统 (新代码，零风险)

**目标：** 创建新目录结构和完整的记忆管理系统，不影响现有代码

| 步骤 | 文件 | 内容 |
|---|---|---|
| 1.1 | `domain/common/interfaces.py` | 通用接口 (IEventPublisher, ILogger, IMemoryStore) |
| 1.2 | `domain/common/value_object.py` | TimeRange, PageRequest, MemoryLevel(enum) |
| 1.3 | `domain/common/exceptions.py` | DomainException, MemoryNotFound 等 |
| 1.4 | `domain/memory/entity.py` | MemoryEntry entity, MemoryLevel enum |
| 1.5 | `domain/memory/value_object.py` | MemoryQuery, MemoryStats, MemorySummary |
| 1.6 | `domain/memory/repository.py` | IMemoryRepository 接口 |
| 1.7 | `infrastructure/persistence/connection.py` | 统一 SQLite 连接管理 (单例, 含 PRAGMA) |
| 1.8 | `infrastructure/persistence/memory_repo.py` | MemoryRepository (SQLite 实现 + ChromaDB 集成) |
| 1.9 | `infrastructure/vector/chroma_store.py` | ChromaDB 封装 (持久化 + 语义检索 + 元数据过滤) |
| 1.10 | `infrastructure/memory/forgetting_curve.py` | Ebbinghaus 遗忘曲线计算 |
| 1.11 | `infrastructure/memory/session_memory.py` | 会话级记忆 (内存 dict，1h 过期) |
| 1.12 | `infrastructure/memory/context_injector.py` | 记忆注入 Agent 上下文的逻辑 |
| 1.13 | `application/dto/memory_dto.py` | 记忆相关 DTO |
| 1.14 | `application/services/memory_service.py` | 记忆应用服务 (CRUD + Chroma 检索 + 遗忘曲线注入) |
| 1.15 | `config/settings.py` | 配置管理 |
| 1.16 | `tests/domain/memory/test_forgetting_curve.py` | 遗忘曲线单元测试 |
| 1.17 | `tests/infrastructure/vector/test_chroma_store.py` | ChromaDB 向量存储测试 |

**验证：** `uv run python -m pytest tests/ -v` 全部通过 + 新增记忆测试通过

### Phase 2: 基础设施层重构

**目标：** 统一数据库连接，重构各 Repository

| 步骤 | 文件 | 内容 |
|---|---|---|
| 2.1 | `infrastructure/persistence/migrations.py` | 数据库迁移版本管理 |
| 2.2 | `domain/agent/repository.py` | IAgentRepository 接口 |
| 2.3 | `infrastructure/persistence/agent_repo.py` | AgentRepository (从 loader.py 提取) |
| 2.4 | `domain/skill/repository.py` | ISkillRepository 接口 |
| 2.5 | `infrastructure/persistence/skill_repo.py` | SkillRepository (从 skills/loader.py 提取) |
| 2.6 | `domain/routing/entity.py` | RoutingDecision, CandidateScore 实体 (从 routing_db.py 迁移) |
| 2.7 | `domain/routing/strategy.py` | IRoutingStrategy 接口 |
| 2.8 | `infrastructure/persistence/routing_repo.py` | RoutingRepository |
| 2.9 | `infrastructure/persistence/token_repo.py` | TokenUsageRepository |
| 2.10 | `domain/contract/repository.py` | IContractRepository 接口 |
| 2.11 | `infrastructure/persistence/contract_repo.py` | ContractRepository (从 contracts.py 提取) |

**验证：** 全部测试通过

### Phase 3: 领域层迁移

**目标：** 将核心业务逻辑迁移到 domain/

| 步骤 | 文件 | 内容 |
|---|---|---|
| 3.1 | `domain/agent/entity.py` | AgentConfig, Agent 实体 (从 generic_agent.py 迁移) |
| 3.2 | `domain/agent/value_object.py` | Capability, SkillRef 值对象 |
| 3.3 | `domain/skill/entity.py` | Skill 实体 (从 skills/loader.py 迁移) |
| 3.4 | `domain/contract/entity.py` | Contract 实体 (从 contracts.py 迁移) |
| 3.5 | `domain/task/entity.py` | Task, TaskResult (从 interfaces.py 迁移) |
| 3.6 | `domain/routing/service.py` | RoutingService (从 integrated_router.py 迁移) |
| 3.7 | `infrastructure/persistence/migrations.py` | 添加 memory 相关表 |

**验证：** 全部测试通过，server.py 能正常启动

### Phase 4: 应用层与接口层

**目标：** 创建应用服务，拆分 admin_console.py

| 步骤 | 文件 | 内容 |
|---|---|---|
| 4.1 | `application/services/agent_service.py` | 智能体应用服务 |
| 4.2 | `application/services/routing_service.py` | 路由应用服务 |
| 4.3 | `application/services/contract_service.py` | 契约应用服务 |
| 4.4 | `application/services/skill_service.py` | 技能应用服务 |
| 4.5 | `interfaces/mcp/server.py` | MCP 服务器迁移 |
| 4.6 | `interfaces/api/routes/memory.py` | 记忆管理 API (新) |
| 4.7 | `interfaces/api/routes/agents.py` | 智能体路由 (从 admin_console.py 拆分) |
| 4.8 | `interfaces/api/routes/contracts.py` | 契约路由 (拆分) |
| 4.9 | `interfaces/api/routes/skills.py` | 技能路由 (拆分) |
| 4.10 | `interfaces/api/admin.py` | admin_console.py 精简版 |
| 4.11 | `core/old_adapters.py` | 旧代码适配新接口 |

**验证：** admin_console.py 和 server.py 入口正常工作

---

## 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| 旧代码 import 路径被破坏 | Phase 1/2 只加新文件不删旧文件，最后阶段才清理 |
| admin_console.py (4700行) 拆分时出错 | 每次拆分一个路由，测试后再拆分下一个 |
| 向量搜索性能 | 使用 ChromaDB 内置 HNSW 索引，无需手动优化 |
| 遗忘曲线导致记忆过早丢失 | 保留率 R < 0.1 才归档，保守阈值 |

---

## 验证方案

1. **每 phase 结束：** `uv run python -m pytest tests/ -v` (全部 26+ 测试通过)
2. **新增测试：** 遗忘曲线计算、向量存储 CRUD、记忆服务 CRUD
3. **手动验证：** `uv run python admin_console.py` 页面正常 + `uv run python server.py` MCP 正常
4. **最终验证：** 记忆读写 → 向量检索 → 上下文注入 完整链路

---

## 依赖变化

```toml
# pyproject.toml 新增
chromadb>=1.10.0      # 轻量向量数据库（替代自定义 BLOB 存储）
```

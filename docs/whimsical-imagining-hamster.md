# Sivan v1.1 升级改造方案

## Context

基于 v1.0 已完成的功能（5 阶段路线图 + P0 基础设施），进行 v1.1 版本升级。核心需求：项目隔离、自主规划 Agent、全新记忆模型、元编排器。本次改造在现有 DDD 架构上增量构建，不破坏现有功能。

---

## 一、项目隔离系统

### 1.1 新增领域层

| 文件 | 内容 |
|------|------|
| `domain/project/entity.py` | `Project` 实体（project_id, name, description, status, created_by, timestamps） |
| `domain/project/repository.py` | `IProjectRepository` 接口（CRUD + KB 分配） |

### 1.2 新增表（Alembic `0002_projects`）

```sql
CREATE TABLE projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE kb_project_assignments (
    kb_name TEXT NOT NULL REFERENCES knowledge_bases(kb_name) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    UNIQUE(kb_name, project_id)
);
```

`conversations.project_id` 字段已存在，无需改 schema，但需初始化 `default` 项目行并补充 FK 约束。

### 1.3 新增基础设施

| 文件 | 说明 |
|------|------|
| `infrastructure/persistence/project_repo.py` | SQLite 实现（`SQLiteConnectionManager`） |
| `application/services/project_service.py` | 应用服务（CRUD + KB 分配/搜索） |
| `interfaces/api/routes/projects.py` | REST API 路由 |

### 1.4 修改现有文件

| 文件 | 改动 |
|------|------|
| `interfaces/api/services/conversations.py` | `list_conversations()` 增加可选 `project_id` 过滤参数 |
| `interfaces/api/routes/conversations.py` | `api_list_conversations()` 增加 `project_id` 查询参数 |
| `application/services/kb_service.py` | 新增 `search_by_kb_names(kb_names, query)`，接受 KB 名称列表限制搜索范围 |
| `infrastructure/persistence/kb_repo.py` | 新增 `get_kb_by_names()` / 向量搜索支持按集合列表筛选 |
| `infrastructure/agents/generic_agent.py` | `_preprocess_context()` 根据 `context["project_id"]` 查询分配的知识库，只搜索这些 KB |
| `config/settings.py` | 增加 `DEFAULT_PROJECT_ID` |

### 1.5 KB 与项目关系

- KB 创建时不绑定项目（现有行为不变）
- `POST /api/projects/{id}/kbs` 分配 KB 到项目
- `DELETE /api/projects/{id}/kbs/{kb_name}` 取消分配
- Agent RAG 搜索时：根据 `project_id` 查 `kb_project_assignments` → 只搜分配的 KB

### 1.6 管理控制台

- 新增 `/projects` 页面（项目列表 + CRUD）
- 项目详情页：对话列表 + KB 分配管理
- `/chat` 页面增加项目选择器（顶部下拉），选定后只显示该项目下的对话

### 1.7 工作量：3-4 天

---

## 二、自主规划 Agent（OrchestratorAgent 重构）

### 2.1 核心改动

**文件：`infrastructure/agents/orchestrator.py`** 从简单聊天回退 Agent 重构为 ReAct 三阶段循环 Agent：

```
阶段 1: 任务分析（Task Analysis）
  LLM 调用输出结构化结果：
  { "decision": "chat"|"single"|"squad",
    "reasoning": "...",
    "topology": { "phases": [...] } | null }

阶段 2: 规划生成（Plan Generation）
  - "squad": 调用 TopologyGenerator 动态生成编排拓扑
  - "single": 确定目标 Agent + 执行计划
  - "chat": 跳过，直接回复

阶段 3: 执行/委托（Execution）
  - "squad": 调用 execute_dynamic_squad() 执行动态拓扑
  - "single": 调用 agent_service.execute()
  - "chat": 直接 LLM 回复（保留现有行为）
```

### 2.2 系统提示词替换

用元编排系统提示替换 `_CHAT_SYSTEM_PROMPT`，包含：
- 角色定义："Sivan 编排智能体"
- 三阶段决策流程图
- 结构化输出格式（JSON schema）
- 决策示例（何时 chat/single/squad）

### 2.3 消息执行流集成

**文件：`interfaces/api/services/conversations.py`**

当前流程 `execute_message_flow`：
1. `_route_task()` 路由
2. `detect_squad()` 匹配
3. `call_agent_for_squad()` 执行

v1.1 流程：
1. `_route_task()` — 显式 @agent 匹配
2. 无匹配时 → `OrchestratorAgent.execute()` — 任务分析
3. Orchestrator 决定：直接回复 / 单 Agent 执行 / 动态 Squad 编排

`squad_matcher.py.detect_squad()` **被废弃**，由 Orchestrator 的 TopologyGenerator 替代。

### 2.4 工作量：4-5 天

---

## 三、新记忆模型

### 3.1 情感权重（Sentiment Boost）

**改动文件：**

| 文件 | 改动 |
|------|------|
| `domain/memory/entity.py` | 新增 `is_important: bool = False` 字段；`calculate_retention()` 中 `is_important` 时稳定系数 ×10 |
| `domain/memory/value_object.py` | `MemoryQuery` 增加 `is_important` 过滤 |
| `infrastructure/persistence/memory_repo.py` | 新增 `is_important` 列读写；`_row_to_entry()` 映射；新增 `find_important()` |
| `infrastructure/memory/forgetting_curve.py` | 函数签名增加 `stability_multiplier` 参数 |
| `infrastructure/persistence/models.py` | `memory_entries` 增加列定义（Alembic alter） |

**Schema 变更：**
```sql
ALTER TABLE memory_entries ADD COLUMN is_important INTEGER DEFAULT 0;
```

**API：**
- `POST /api/memory/{memory_id}/important` — 切换重要标记

### 3.2 情境闪现（Context Flashback）

**新增：`infrastructure/memory/flashback_scanner.py`**

```python
class FlashbackScanner:
    def scan(self, current_context: str, scope_ids: dict) -> list[dict]:
        """扫描 retention < 0.3 的记忆，计算与当前上下文的语义相似度，
        匹配 > 0.85 时以 '你可能想起来了...' 前缀注入。"""
```

- 使用现有 ChromaStore 计算向量相似度
- 扫描有上限（max 200 条候选）
- 结果注入到 `ContextInjector.build_context()` 输出中
- 若用户确认有用（通过反馈 API），重置 retention=1.0

**改动文件：`infrastructure/memory/context_injector.py`**
- 集成 FlashbackScanner，扫描结果以特殊前缀 `[情境闪现]` 注入

### 3.3 强化回路 / 本能模板（Instinct Patterns）

**新增表：**
```sql
CREATE TABLE instinct_patterns (
    pattern_id     TEXT PRIMARY KEY,
    task_type      TEXT NOT NULL,
    task_signature TEXT NOT NULL,      -- 归一化任务特征
    topology_json  TEXT NOT NULL,       -- 冻结的编排拓扑
    success_count  INTEGER DEFAULT 0,
    total_count    INTEGER DEFAULT 0,
    confidence     REAL DEFAULT 0.0,
    is_active      INTEGER DEFAULT 0,  -- ≥10 次成功且 confidence>0.8 时激活
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**新增文件：**

| 文件 | 说明 |
|------|------|
| `domain/memory/instinct.py` | `InstinctPattern` 实体 |
| `infrastructure/memory/instinct_repo.py` | 存储实现 + CRUD + `find_matching(task_signature)` |

**执行流程：**
1. Squad 执行成功 → 归一化 task → 查找/创建 pattern
2. 更新 success_count；≥10 且成功率 >80% 激活
3. 下次同类任务 → 跳过动态生成，直接使用冻结拓扑

### 3.4 工作量：5-6 天

---

## 四、元编排器（Meta-Orchestrator）

### 4.1 新增领域层

**`domain/orchestration/topology_generator.py`**

```python
class TopologyGenerator:
    """
    根据任务特征动态生成最优编排拓扑。

    生成策略（按优先级）：
    1. 本能模板匹配 — 同等任务有过成功路径？直接复用
    2. LLM 分析 — 分析任务特征，输出拓扑结构
    3. 默认回退 — sequential 单阶段

    输出示例：
    {
        "phases": [
            {"phase": 1, "mode": "sequential", "agents": ["security-auditor", "architect"],
             "description": "信息收集与架构分析"},
            {"phase": 2, "mode": "parallel", "agents": ["be-dev", "fe-dev", "devops"],
             "description": "并行开发"},
        ]
    }
    """
```

### 4.2 五种编排模式触发条件

| 模式 | 触发特征 |
|------|----------|
| **串行** | 存在明确前后依赖（pipeline、step_by_step、dependency_chain） |
| **并行** | 子任务独立无依赖（independent_subtasks、research、data_collection） |
| **条件分支** | 需根据中间结果决策（decision_tree、branching、if_then_else） |
| **层次** | 复杂度超出单层 Squad 能力（recursive、nested_expertise、sub_delegation） |
| **共识** | 安全/合规/架构等高风领域（high_stakes、review、validation） |

### 4.3 反馈学习

**新增：`domain/orchestration/feedback_learner.py`**

```python
class TopologyFeedbackLearner:
    """记录任务特征→拓扑映射的用户满意度，驱动编排风格演化。"""

    def record_outcome(self, task_signature: str, topology: str, satisfaction: float):
        """存储满意度评分。"""

    def get_preferred_topology(self, task_signature: str) -> str | None:
        """返回该任务类型满意度最高的拓扑。"""
```

**新增表 `topology_feedback`：**
```sql
CREATE TABLE topology_feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_signature TEXT NOT NULL,
    topology       TEXT NOT NULL,
    satisfaction   REAL NOT NULL,
    execution_id   TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 Squad 执行引擎变化

**新建函数 `execute_dynamic_squad()` 在 `interfaces/api/services/squads.py` 中：**

- 接收动态拓扑 dict（非预设 squad_id）
- 创建临时 squad 执行记录或直接调用 phase 执行器
- 执行完毕后可选择清理临时记录

**现有执行引擎（`_execute_phase_sequential` 等 5 个模式）完全保留不变。** 元编排器只替换"如何定义编排"，不替换"如何执行编排"。

### 4.5 `squad_matcher.py` 废弃

`detect_squad()` 硬编码匹配逻辑**完全移除**，由 Orchestrator 的完整决策流程替代。

### 4.6 工作量：5-6 天

---

## 五、路由策略

保持不变。现有实现已完整覆盖需求，无需改动。

---

## 数据流（v1.1）

```
用户消息
    │
    ▼
RoutingService.route()  ──→ 显式 @agent?  ──→ 直接执行
    │
    ▼ (未匹配)
OrchestratorAgent（ReAct 三阶段）
    │
    ├─ chat → 直接 LLM 回复
    ├─ single → agent_service.execute() + 项目级 RAG
    └─ squad → TopologyGenerator
                   │
                   ├─ 本能模板命中 → 复用冻结拓扑
                   ├─ LLM 生成拓扑 → execute_dynamic_squad()
                   │                      │
                   │                      ▼
                   │               Phase 执行引擎（5 模式）
                   │                      │
                   │                      ▼
                   │               FeedbackLearner.record()
                   │                      │
                   │                      ▼
                   │               InstinctRepo.track()
                   └─ 用户反馈 → TopologyFeedbackLearner
```

---

## 构建顺序

```
第 1 周: 基础设施
  Day 1-2:  Project 实体 + Repo + Service + API 路由
  Day 3-4:  KB-Project 关联 + 对话作用域
  Day 5:    数据库迁移（4 张新表）

第 2 周: 记忆升级
  Day 1-2:  情感权重（entity, repo, forgetting_curve）
  Day 3-4:  情境闪现扫描器 + context_injector 集成
  Day 5:    本能模板（entity, repo, 集成）

第 3 周: 编排升级
  Day 1-2:  OrchestratorAgent ReAct 循环
  Day 3-4:  TopologyGenerator + 动态拓扑执行
  Day 5:    FeedbackLearner + squad_matcher 废弃

第 4 周: 集成 + 管理控制台
  Day 1-2:  全链路集成测试
  Day 3:    API 路由调整 + 管理控制台页面
  Day 4-5:  性能优化 + 文档更新
```

---

## 验证方案

1. **项目隔离**: 创建项目 A 和 B → 各分配不同 KB → 在项目中对话 → Agent RAG 只搜到本项目的 KB
2. **OrchestratorAgent**: 发送复杂任务 "做一次完整的系统安全评估" → 确认 Orchestrator 自动生成多阶段拓扑 → 各阶段正确执行
3. **新记忆模型**:
   - 标记记忆为重要 → 10 天后 retention 仍接近 1.0
   - 输入与低 retention 记忆语义相似的消息 → 自动触发情境闪现
   - 同一类型任务连续成功 10 次 → 生成本能模板 → 下次直接走快速通道
4. **元编排器**: 不同任务生成不同拓扑（安全评估→共识为主；功能开发→串行为主；覆盖五种编排拓扑模型）
5. **路由策略**: 现有行为无退化

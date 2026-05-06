"""基于 DDD 架构的 Sivan MCP 服务器。

使用新的 DDD 应用服务构建，不依赖旧 core/ 模块。
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from application.services.agent_service import AgentService
from application.services.contract_service import ContractService
from application.services.kb_service import KnowledgeBaseService
from application.services.routing_service import RoutingService as RoutingAppService
from application.services.skill_service import SkillService
from config.settings import settings
from domain.routing.service import RoutingService as DomainRoutingService
from infrastructure.persistence.agent_repo import AgentRepository
from infrastructure.persistence.connection import SQLiteConnectionManager
from infrastructure.persistence.contract_repo import ContractRepository
from infrastructure.persistence.kb_repo import KnowledgeBaseRepository
from infrastructure.persistence.routing_repo import RoutingRepository
from infrastructure.persistence.skill_repo import SkillRepository
from infrastructure.rag.embedding import BGEChineseEmbedding
from infrastructure.vector.kb_chroma_store import KnowledgeBaseChromaStore

logger = logging.getLogger("sivan.mcp")


# ---- MCP 认证中间件 ----

class MCPAuthMiddleware:
    """ASGI 中间件：验证 MCP HTTP 请求的 Authorization header。

    仅当 settings.MCP_API_KEY 非空时启用。
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if not settings.MCP_API_KEY:
            await self.app(scope, receive, send)
            return

        # 仅拦截 HTTP 请求
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # OPTIONS 放行（CORS preflight）
        if scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # 从 Authorization header 提取 Bearer token
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        if auth_header.startswith("Bearer ") and auth_header[7:] == settings.MCP_API_KEY:
            await self.app(scope, receive, send)
            return

        # 无有效 key → 401
        response_body = json.dumps({"error": "未授权：请在 Authorization header 中提供有效的 MCP_API_KEY"}).encode()
        headers = [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(response_body)).encode()),
        ]
        await send({
            "type": "http.response.start",
            "status": 401,
            "headers": headers,
        })
        await send({
            "type": "http.response.body",
            "body": response_body,
        })


app = FastMCP("Sivan")


# ---- 系统上下文：装配所有 DDD 服务 ----


class SystemContext:
    """DDD 系统上下文，组合所有应用服务和基础组件。"""

    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or settings.PROJECT_ROOT
        self.db_path = settings.DB_PATH

        # 基础设施
        self._conn_mgr = SQLiteConnectionManager(self.db_path)

        # 仓库
        self._routing_repo = RoutingRepository(self._conn_mgr)
        self._contract_repo = ContractRepository(self._conn_mgr)
        self._skill_repo = SkillRepository(self._conn_mgr)

        # 知识库向量存储 + 仓储（放在 agent_repo 之前）
        self._kb_vector = KnowledgeBaseChromaStore(
            persist_dir=settings.CHROMA_PATH,
            embedding_function=BGEChineseEmbedding(),
        )
        self._kb_repo = KnowledgeBaseRepository(self._conn_mgr, self._kb_vector)
        self.kb_service = KnowledgeBaseService(self._kb_repo, self._kb_vector)

        # Agent 仓库（需 kb_service 注入）
        self._agent_repo = AgentRepository(self._conn_mgr, kb_service=self.kb_service)

        # 领域服务（初始化后由 RoutingAppService 装配完整策略）
        _domain_routing = DomainRoutingService(
            strategies={},
            default_strategy="adaptive",
        )

        # 应用服务（内部装配所有 5 种路由策略）
        self.routing_service = RoutingAppService(
            domain_service=_domain_routing,
            routing_repo=self._routing_repo,
            model_dir=str(settings.DATA_DIR / "models"),
        )
        self.agent_service = AgentService(self._agent_repo)
        self.contract_service = ContractService(self._contract_repo)
        self.skill_service = SkillService(self._skill_repo)

        # 注册智能体到路由
        self._register_agents()

    def _register_agents(self) -> None:
        """将可用智能体注册到路由系统。

        注：orchestrator 是系统代码层调度器，不注册到路由，
        避免路由决策将其选中执行领域任务。
        """
        agents = self._agent_repo.find_all_active()
        for agent_name, agent in agents.items():
            if agent_name == "orchestrator":
                continue
            capabilities = agent.get_capabilities()
            self.routing_service.add_agent(agent_name, capabilities)

    def get_agent_definitions(self) -> dict[str, dict[str, Any]]:
        """获取智能体定义元数据。"""
        conn = SQLiteConnectionManager.get_instance(self.db_path).connection
        conn.row_factory = sqlite3.Row
        definitions: dict[str, dict[str, Any]] = {}
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agents WHERE status = 'active'")
        for row in cursor.fetchall():
            import json as _json
            row_dict = dict(row)
            definitions[row_dict["agent_id"]] = {
                "name": row_dict["agent_id"],
                "display_name": row_dict.get("display_name", ""),
                "description": row_dict.get("description", "") or "",
                "version": row_dict.get("version", "1.0.0"),
                "type": "base",
                "skills": _json.loads(row_dict["skill_ids"]) if row_dict.get("skill_ids") else [],
                "tool_permissions": _json.loads(row_dict["tools"]) if row_dict.get("tools") else [],
            }
        return definitions


_system: SystemContext | None = None


def get_system() -> SystemContext:
    """获取系统上下文单例。"""
    global _system
    if _system is None:
        _system = SystemContext()
    return _system


# ==================== MCP 工具 ====================


@app.tool()
async def list_agents() -> str:
    """列出所有可用智能体。"""
    system = get_system()
    agents_list = system.agent_service.list_agents()
    definitions = system.get_agent_definitions()
    agents = system._agent_repo.find_all_active()

    if not agents:
        return "当前没有可用的智能体"

    result = "## 可用智能体\n\n"
    for agent_name, agent in agents.items():
        adef = definitions.get(agent_name, {})
        result += f"### {adef.get('display_name', agent_name)}\n"
        result += f"- **名称**: `{agent_name}`\n"
        result += f"- **类型**: {adef.get('type', 'base')}\n"
        result += f"- **版本**: {adef.get('version', 'N/A')}\n"
        result += f"- **描述**: {str(adef.get('description', 'N/A')).strip()[:100]}\n"
        result += f"- **技能**: {', '.join(adef.get('skills', []))}\n"
        result += f"- **工具权限**: {', '.join(adef.get('tool_permissions', []))}\n\n"
    return result


@app.tool()
async def call_agent(agent_name: str, task: str, context: str | None = None) -> str:
    """调用特定智能体执行任务。

    Args:
        agent_name: 智能体名称 (如: be-dev, fe-dev)
        task: 任务描述
        context: 可选上下文 (JSON 格式)
    """
    system = get_system()
    task_context = {}
    if context:
        try:
            task_context = json.loads(context)
        except json.JSONDecodeError as e:
            return f"上下文格式错误: {e}"

    output = system.agent_service.execute(agent_name, task, task_context)

    result = "## 任务执行结果\n\n"
    result += f"**智能体**: {agent_name}\n"
    result += f"**输出**:\n{output}"
    return result


@app.tool()
async def orchestrator_route(user_input: str, context: str | None = None) -> str:
    """Orchestrator 路由：分析用户输入并路由到最合适的智能体。

    所有消息必经 OrchestratorAgent 分析决策：
    - chat → 直接回复
    - single → 委托对应智能体执行
    - squad → 多智能体编排

    Args:
        user_input: 用户输入的自然语言请求
        context: 可选上下文 (JSON 格式)
    """
    system = get_system()

    task_context = {}
    if context:
        try:
            task_context = json.loads(context)
        except json.JSONDecodeError as e:
            return f"上下文格式错误: {e}"

    # 调用 OrchestratorAgent 分析决策
    result = system.agent_service.execute("orchestrator", user_input, task_context)

    try:
        decision = json.loads(result)
    except json.JSONDecodeError:
        return f"## 分析失败\n\nOrchestrator 返回了非结构化结果:\n{result}"

    if decision.get("decision") == "chat":
        return f"## 聊天回复\n\n{decision.get('response', '')}"

    agent_name = decision.get("agent", "") if decision.get("decision") == "single" else ""

    if decision.get("decision") == "single" and agent_name:
        refined_task = decision.get("refined_task", user_input)

        # AgentResolver 解析语义化 agent 名称
        from application.services.agent_resolver import AgentResolver
        resolver = AgentResolver(str(system.db_path))
        resolved = resolver.resolve_agent(agent_name)
        if resolved:
            agent_name = resolved
        elif resolver._should_create_agent(agent_name):
            new_id = resolver.create_agent(agent_name, task_description=user_input)
            system.agent_service.reload(new_id)
            agent_name = new_id
        else:
            return f"未找到匹配的智能体: {agent_name}"

        output = system.agent_service.execute(agent_name, refined_task, task_context)
        result_text = "## Orchestrator 路由结果\n\n"
        result_text += f"**用户输入**: {user_input}\n\n"
        result_text += f"**路由决策**: 匹配到智能体 `{agent_name}`\n\n"
        result_text += f"**执行结果**:\n\n{output}"
        return result_text

    if decision.get("decision") == "squad":
        topology = decision.get("topology", {})
        return "## Squad 编排\n\n需要多智能体协作:\n"
        "```json\n"
        f"{json.dumps(topology, ensure_ascii=False, indent=2)}\n"
        "```\n\n"
        "请通过 Web 控制台查看编排进度。"

    return f"## 未知决策\n\nOrchestrator 返回了无法处理的决策:\n```json\n{json.dumps(decision, ensure_ascii=False, indent=2)}\n```"


@app.tool()
async def create_contract(contract_type: str, content: str, created_by: str = "mcp_user") -> str:
    """创建契约。

    Args:
        contract_type: 契约类型 (global, api, ui, data, model)
        content: 契约内容 (JSON 格式)
        created_by: 创建者
    """
    system = get_system()
    try:
        contract_data = json.loads(content)
        contract_id = system.contract_service.create(contract_type, contract_data, created_by)
        contract = system.contract_service.get(contract_id)

        result = "## 契约创建成功\n\n"
        result += f"- **ID**: `{contract_id}`\n"
        result += f"- **类型**: {contract_type}\n"
        if contract:
            result += f"- **状态**: {contract.get('status', 'draft')}\n"
            result += f"- **版本**: {contract.get('version', '1.0.0')}\n"
            tags = contract.get('tags', [])
            if tags:
                result += f"- **标签**: {', '.join(tags)}\n"
        return result
    except json.JSONDecodeError as e:
        return f"契约内容必须是有效的 JSON 格式: {e}"
    except Exception as e:
        return f"创建契约失败: {e}"


@app.tool()
async def list_contracts(
    contract_type: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    limit: int = 50,
) -> str:
    """列出契约。

    Args:
        contract_type: 可选类型过滤 (global, api, ui, data, model)
        status: 可选状态过滤 (draft, reviewed, approved, deprecated)
        tag: 可选标签过滤
        limit: 返回数量限制
    """
    system = get_system()
    contracts = system.contract_service.find(contract_type, status, tag, limit)

    if not contracts:
        return "没有找到匹配的契约"

    result = "## 契约列表\n\n"
    result += f"**总数**: {len(contracts)}\n\n"

    for contract in contracts:
        result += f"### `{contract.get('contract_id', 'unknown')}`\n"
        result += f"- **类型**: {contract.get('contract_type', 'unknown')}\n"
        result += f"- **状态**: {contract.get('status', 'unknown')}\n"
        result += f"- **版本**: {contract.get('version', '1.0.0')}\n"
        tags = contract.get('tags', [])
        if tags:
            result += f"- **标签**: {', '.join(tags)}\n"
        result += "\n"
    return result


@app.tool()
async def contract_stats() -> str:
    """获取契约统计信息。"""
    system = get_system()
    try:
        stats = system.contract_service.get_stats()
        result = "## 契约统计\n\n"
        result += f"- **总契约数**: {stats.get('total_contracts', 0)}\n"
        type_stats = stats.get('by_type', {})
        if type_stats:
            result += "\n### 按类型\n"
            for ct, counts in type_stats.items():
                result += f"- **{ct}**: {counts.get('total', 0)} 个\n"
        return result
    except Exception as e:
        return f"获取统计失败: {e}"


@app.tool()
async def system_status() -> str:
    """获取系统状态。"""
    system = get_system()
    agents = system._agent_repo.find_all_active()

    result = "## Sivan 系统状态\n\n"
    result += f"- **智能体数量**: {len(agents)}\n"
    result += f"- **数据库**: {system.db_path}\n"
    result += f"- **项目目录**: {system.project_root}\n\n"
    result += "### 可用工具\n"
    result += "1. `list_agents` - 列出智能体\n"
    result += "2. `call_agent` - 调用智能体\n"
    result += "3. `orchestrator_route` - 智能体路由\n"
    result += "4. `create_contract` - 创建契约\n"
    result += "5. `list_contracts` - 列出契约\n"
    result += "6. `contract_stats` - 契约统计\n"
    result += "7. `system_status` - 系统状态\n"
    result += "8. `routing_analytics` - 路由分析\n"
    result += "9. `agent_performance` - 智能体性能\n"
    result += "10. `recent_routing_decisions` - 最近路由决策\n"
    result += "11. `provide_routing_feedback` - 提供路由反馈\n"
    result += "12. `search_knowledgebase` - 搜索知识库\n"
    result += "13. `list_knowledgebases` - 知识库列表\n"
    result += "14. `ingest_kb_document` - 导入文档到知识库\n"
    return result


@app.tool()
async def routing_analytics() -> str:
    """获取路由分析数据。"""
    system = get_system()
    analytics = system.routing_service.get_analytics()

    if "error" in analytics:
        return f"获取路由分析失败: {analytics['error']}"

    result = "## 路由决策分析\n\n"

    if "database" in analytics:
        db = analytics["database"]
        result += "### 数据库统计\n"
        result += f"- **总决策数**: {db.get('total_decisions', 0)}\n"
        result += f"- **成功率**: {db.get('success_rate', 0):.1%}\n"
        result += f"- **平均执行时间**: {db.get('avg_execution_time_ms', 0):.2f}ms\n"
        result += f"- **平均置信度**: {db.get('avg_confidence_score', 0):.2f}\n"

    if "routers" in analytics:
        routers = analytics["routers"]
        result += "\n### 路由器性能\n"
        if "semantic" in routers:
            s = routers["semantic"]
            result += f"- **语义路由器**: {s.get('total_semantic_features', 0)} 个同义词特征, jieba 分词\n"
        if "ml" in routers:
            m = routers["ml"]
            trained = m.get("is_trained", False)
            result += f"- **ML 路由器**: {'已训练' if trained else '未训练'} (scikit-learn TF-IDF + 集成分类器)\n"
        if "adaptive" in routers:
            a = routers["adaptive"]
            w = a.get("weights", {})
            names = a.get("strategy_names", [])
            weight_str = ", ".join(f"{n}: {w.get(n, 0):.2f}" for n in names) if w else "未计算"
            result += f"- **自适应路由器**: {len(names)} 个子策略, 权重: {weight_str}\n"

    if "strategy_performance" in analytics:
        sp = analytics["strategy_performance"]
        if sp:
            result += "\n### 策略性能对比\n"
            for p in sp:
                result += (
                    f"- **{p['strategy_name']}**: "
                    f"决策 {p.get('total_decisions', 0)} 次, "
                    f"成功率 {p.get('success_rate', 0):.1%}"
                )
                if p.get("avg_execution_time_ms"):
                    result += f", 平均耗时 {p['avg_execution_time_ms']:.0f}ms"
                result += "\n"
    return result


@app.tool()
async def agent_performance(agent_name: str) -> str:
    """获取智能体性能数据。

    Args:
        agent_name: 智能体名称
    """
    system = get_system()
    perf = system.routing_service.get_agent_performance(agent_name)

    if "error" in perf:
        return f"获取性能数据失败: {perf['error']}"

    result = f"## 智能体性能: {agent_name}\n\n"
    result += f"- **总任务数**: {perf.get('total_tasks', 0)}\n"
    if perf.get("success_rate") is not None:
        result += f"- **成功率**: {perf['success_rate']:.1%}\n"
    if perf.get("avg_confidence") is not None:
        result += f"- **平均置信度**: {perf['avg_confidence']:.2f}\n"
    if perf.get("avg_execution_time_ms") is not None:
        result += f"- **平均执行时间**: {perf['avg_execution_time_ms']:.2f}ms\n"
    return result


@app.tool()
async def recent_routing_decisions(limit: int = 10) -> str:
    """查看最近的路由决策。

    Args:
        limit: 返回数量
    """
    system = get_system()
    decisions = system.routing_service.get_recent_decisions(limit)

    result = f"## 最近路由决策 (共 {len(decisions)} 条)\n\n"
    for i, d in enumerate(decisions, 1):
        result += f"### #{i}: ID {d.get('id', 'N/A')}\n"
        result += f"- **任务**: {str(d.get('task_description', ''))[:100]}\n"
        result += f"- **路由到**: {d.get('selected_agent', '无')}\n"
        result += f"- **策略**: {d.get('routing_strategy', 'unknown')}\n"
        result += f"- **状态**: {d.get('status', 'unknown')}\n"
        result += f"- **时间**: {d.get('created_at', 'N/A')}\n\n"
    return result


@app.tool()
async def provide_routing_feedback(decision_id: str, success: bool) -> str:
    """提供路由决策反馈。

    Args:
        decision_id: 决策 ID (数字)
        success: 是否成功
    """
    system = get_system()
    try:
        did = int(decision_id)
        ok = system.routing_service.provide_feedback(did, success)
        if ok:
            return f"反馈已记录: 决策 #{decision_id} -> {'成功' if success else '失败'}"
        return "记录反馈失败，请检查决策 ID"
    except ValueError:
        return "决策 ID 必须是数字"


# ==================== 知识库工具 ====================


@app.tool()
async def search_knowledgebase(query: str, kb_name: str | None = None,
                                top_k: int = 5) -> str:
    """搜索知识库，获取与查询相关的文档内容。

    智能体应主动使用此工具检索相关文档，之后再回答用户问题。

    Args:
        query: 搜索查询语句
        kb_name: 可选，指定知识库名称；不指定则搜索所有知识库
        top_k: 返回结果数量 (默认 5)
    """
    system = get_system()
    try:
        if kb_name:
            results = system.kb_service.search(kb_name, query, top_k)
        else:
            results = system.kb_service.search_all(query, top_k)

        if not results:
            return f"未在知识库中找到相关内容：{query}"

        output = f"## 知识库检索结果\n\n**查询**: {query}\n"
        if kb_name:
            output += f"**知识库**: {kb_name}\n"
        output += f"**结果数**: {len(results)}\n\n"

        for i, r in enumerate(results, 1):
            meta = r.get("metadata", {})
            source = meta.get("source", "未知")
            heading = meta.get("heading", "")
            heading_fmt = f" > {heading}" if heading else ""
            score = r.get("score", 0)
            output += f"### {i}. [{r['kb_name']}]{heading_fmt} ({source})\n"
            output += f"**相关度**: {score:.3f}\n"
            output += f"**内容**:\n{r['text'][:500]}\n\n"

        return output
    except Exception as e:
        return f"知识库检索失败: {e}"


@app.tool()
async def list_knowledgebases() -> str:
    """列出所有可用知识库及其统计信息。"""
    system = get_system()
    kbs = system.kb_service.list_knowledge_bases()

    if not kbs:
        return "当前没有知识库。可以通过 ingest_kb_document 命令导入文档创建知识库。"

    output = "## 知识库列表\n\n"
    for kb in kbs:
        output += f"### {kb['kb_name']}\n"
        output += f"- **描述**: {kb.get('description', '')}\n"
        output += f"- **文档数**: {kb.get('document_count', 0)}\n"
        output += f"- **分块数**: {kb.get('chunk_count', 0)}\n"
        output += f"- **创建时间**: {kb.get('created_at', '')}\n\n"
    return output


@app.tool()
async def ingest_kb_document(kb_name: str, file_path: str) -> str:
    """将文档导入知识库。支持 txt、md、pdf 格式。

    智能体在处理任务前，先使用此工具导入相关文档，然后用 search_knowledgebase 检索。

    Args:
        kb_name: 目标知识库名称（不存在则自动创建）
        file_path: 文档路径（绝对路径）
    """
    system = get_system()
    try:
        result = system.kb_service.ingest_file(kb_name, file_path)
        return (
            f"## 文档导入成功\n\n"
            f"- **知识库**: {kb_name}\n"
            f"- **文档**: {result['filename']}\n"
            f"- **字符数**: {result['char_count']}\n"
            f"- **分块数**: {result['chunk_count']}\n"
        )
    except Exception as e:
        return f"文档导入失败: {e}"


# ==================== 主函数 ====================


def main(transport: str | None = None) -> None:
    """主函数。

    Args:
        transport: 传输协议 ("stdio", "http", "sse", "streamable-http")，
                   默认使用 settings.transport (默认 stdio)。
    """
    print("=" * 70)
    print("Sivan MCP 服务器 (DDD 架构)")
    print("=" * 70)
    ctx = get_system()
    agents = ctx._agent_repo.find_all_active()
    print(f"已加载 {len(agents)} 个智能体")
    print(f"数据库: {ctx.db_path}")

    # 恢复上次异常中断的消息（pending/running → failed）
    try:
        from interfaces.api.services.conversations import recover_stuck_messages
        stuck = recover_stuck_messages(ctx.db_path)
        if stuck:
            print(f"✅ 已恢复 {stuck} 条卡住的消息")
    except Exception:
        pass

    if settings.MCP_API_KEY:
        if transport in ("http", "sse", "streamable-http", None):
            print("🔑 MCP 认证已启用：使用 MCP_API_KEY")
        else:
            print("⚠️  MCP_API_KEY 已设置，但 STDIO 传输不支持认证")

    print("=" * 70)

    run_kwargs: dict[str, Any] = {}
    if transport:
        run_kwargs["transport"] = transport

    resolved_transport = transport or "stdio"
    if settings.MCP_API_KEY and resolved_transport in ("http", "sse", "streamable-http"):
        from starlette.middleware import Middleware
        run_kwargs["middleware"] = [Middleware(MCPAuthMiddleware)]

    print("\n服务器正在运行...")
    app.run(**run_kwargs)

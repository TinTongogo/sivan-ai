"""Squad 数据访问服务与执行引擎。"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect

logger = logging.getLogger(__name__)


def get_squads_list(db_path: str | Path) -> list[dict[str, Any]]:
    """获取Squad列表。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT squad_id, name, description, version, status, category, execution_count, success_count, created_at, updated_at "
            "FROM squads ORDER BY created_at DESC"
        )
        squads = []
        for row in cursor.fetchall():
            s = dict(row)
            cursor.execute("SELECT COUNT(*) as agent_count FROM squad_agents WHERE squad_id = ?", (s["squad_id"],))
            agent_count_row = cursor.fetchone()
            s["agent_count"] = agent_count_row["agent_count"] if agent_count_row else 0
            squads.append(s)
        conn.close()
        return squads
    except Exception:
        return []


def get_squad_detail(db_path: str | Path, squad_id: str) -> dict[str, Any]:
    """获取Squad详情（包含阶段和智能体）。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM squads WHERE squad_id = ?", (squad_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"error": "Squad not found"}
        squad = dict(row)

        cursor.execute(
            "SELECT phase, name, description, mode, parent_phase, conditions_json, consensus_threshold, "
            "estimated_duration_hours, max_duration_hours, sort_order "
            "FROM squad_workflows WHERE squad_id = ? ORDER BY sort_order, phase",
            (squad_id,),
        )
        phases = []
        for wf_row in cursor.fetchall():
            phase = dict(wf_row)
            p = phase["phase"]
            if phase.get("conditions_json"):
                try:
                    phase["conditions_json"] = json.loads(phase["conditions_json"])
                except Exception:
                    phase["conditions_json"] = None
            cursor.execute(
                "SELECT agent_name, role, sort_order, is_lead, weight, conditions_json "
                "FROM squad_agents WHERE squad_id = ? AND phase = ? ORDER BY is_lead DESC, sort_order, agent_name",
                (squad_id, p),
            )
            agent_list = []
            for a_row in cursor.fetchall():
                agent = dict(a_row)
                if agent.get("conditions_json"):
                    try:
                        agent["conditions_json"] = json.loads(agent["conditions_json"])
                    except Exception:
                        agent["conditions_json"] = None
                agent_list.append(agent)
            phase["agents"] = agent_list
            phases.append(phase)
        squad["phases"] = phases

        for jf in ["quality_gates_json", "success_metrics_json"]:
            if squad.get(jf):
                try:
                    squad[jf] = json.loads(squad[jf])
                except Exception:
                    squad[jf] = {}
        conn.close()
        return squad
    except Exception as e:
        return {"error": str(e)}


def get_squads_stats(db_path: str | Path) -> dict[str, Any]:
    """获取Squad统计。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(*) as total FROM squads")
        stats["total"] = cursor.fetchone()["total"]
        cursor.execute("SELECT status, COUNT(*) as count FROM squads GROUP BY status")
        stats["by_status"] = {r["status"]: r["count"] for r in cursor.fetchall()}
        cursor.execute("SELECT category, COUNT(*) as count FROM squads WHERE category IS NOT NULL GROUP BY category")
        stats["by_category"] = {r["category"]: r["count"] for r in cursor.fetchall()}
        cursor.execute("SELECT SUM(execution_count) as total_executions FROM squads")
        stats["total_executions"] = cursor.fetchone()["total_executions"] or 0
        cursor.execute("SELECT SUM(success_count) as total_successes FROM squads")
        stats["total_successes"] = cursor.fetchone()["total_successes"] or 0
        cursor.execute("SELECT squad_id, name, execution_count FROM squads ORDER BY execution_count DESC LIMIT 5")
        stats["most_active"] = [dict(r) for r in cursor.fetchall()]
        cursor.execute(
            "SELECT squad_id, name, CASE WHEN execution_count > 0 THEN success_count * 100.0 / execution_count ELSE 0 END as success_rate "
            "FROM squads WHERE execution_count > 0 ORDER BY success_rate DESC LIMIT 5"
        )
        stats["most_successful"] = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return stats
    except Exception:
        return {}


def create_squad(db_path: str | Path, squad_data: dict[str, Any]) -> dict[str, Any]:
    """创建新Squad。"""
    try:
        squad_id = squad_data.get("squad_id")
        if not squad_id:
            return {"success": False, "error": "squad_id is required"}
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT squad_id FROM squads WHERE squad_id = ?", (squad_id,))
        if cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Squad {squad_id} already exists"}

        cursor.execute(
            "INSERT INTO squads (squad_id, name, description, version, status, category, workflow_type, "
            "max_parallel_agents, estimated_duration_days, quality_gates_json, success_metrics_json, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (squad_id, squad_data.get("name", ""), squad_data.get("description", ""),
             squad_data.get("version", "1.0.0"), squad_data.get("status", "active"),
             squad_data.get("category"), squad_data.get("workflow_type", "sequential"),
             squad_data.get("max_parallel_agents", 1), squad_data.get("estimated_duration_days", 7),
             json.dumps(squad_data.get("quality_gates", [])),
             json.dumps(squad_data.get("success_metrics", {})), squad_data.get("created_by", "system")),
        )

        for phase in squad_data.get("phases", []):
            p = phase.get("phase", 1)
            cursor.execute(
                "INSERT INTO squad_workflows (squad_id, phase, name, description, mode, parent_phase, conditions_json, "
                "consensus_threshold, estimated_duration_hours, max_duration_hours, sort_order) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (squad_id, p, phase.get("name", ""), phase.get("description", ""), phase.get("mode", "sequential"),
                 phase.get("parent_phase"), json.dumps(phase.get("conditions", None), ensure_ascii=False),
                 phase.get("consensus_threshold", 0.5), phase.get("estimated_duration_hours", 24),
                 phase.get("max_duration_hours", 48), phase.get("sort_order", p * 10)),
            )
            for agent in phase.get("agents", []):
                cursor.execute(
                    "INSERT INTO squad_agents (squad_id, phase, agent_name, role, sort_order, is_lead, weight, conditions_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (squad_id, p, agent.get("agent_name"), agent.get("role", ""), agent.get("sort_order", 0),
                     1 if agent.get("is_lead") else 0, agent.get("weight", 1.0),
                     json.dumps(agent.get("conditions", None), ensure_ascii=False)),
                )
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Squad {squad_id} created successfully", "squad_id": squad_id}
    except Exception as e:
        return {"success": False, "error": _format_squad_error(e)}


def update_squad(db_path: str | Path, squad_id: str, squad_data: dict[str, Any]) -> dict[str, Any]:
    """更新Squad。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT squad_id FROM squads WHERE squad_id = ?", (squad_id,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Squad {squad_id} not found"}
        cursor.execute(
            "UPDATE squads SET name=?, description=?, version=?, status=?, category=?, workflow_type=?, "
            "max_parallel_agents=?, estimated_duration_days=?, quality_gates_json=?, success_metrics_json=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE squad_id=?",
            (squad_data.get("name", ""), squad_data.get("description", ""), squad_data.get("version", "1.0.0"),
             squad_data.get("status", "active"), squad_data.get("category"), squad_data.get("workflow_type", "sequential"),
             squad_data.get("max_parallel_agents", 1), squad_data.get("estimated_duration_days", 7),
             json.dumps(squad_data.get("quality_gates", [])), json.dumps(squad_data.get("success_metrics", {})), squad_id),
        )
        if "phases" in squad_data:
            cursor.execute("DELETE FROM squad_agents WHERE squad_id = ?", (squad_id,))
            cursor.execute("DELETE FROM squad_workflows WHERE squad_id = ?", (squad_id,))
            for phase in squad_data["phases"]:
                p = phase.get("phase", 1)
                cursor.execute(
                    "INSERT INTO squad_workflows (squad_id, phase, name, description, mode, parent_phase, conditions_json, "
                    "consensus_threshold, estimated_duration_hours, max_duration_hours, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (squad_id, p, phase.get("name", ""), phase.get("description", ""), phase.get("mode", "sequential"),
                     phase.get("parent_phase"), json.dumps(phase.get("conditions", None), ensure_ascii=False),
                     phase.get("consensus_threshold", 0.5), phase.get("estimated_duration_hours", 24),
                     phase.get("max_duration_hours", 48), phase.get("sort_order", p * 10)),
                )
                for agent in phase.get("agents", []):
                    cursor.execute(
                        "INSERT INTO squad_agents (squad_id, phase, agent_name, role, sort_order, is_lead, weight, conditions_json) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (squad_id, p, agent.get("agent_name"), agent.get("role", ""), agent.get("sort_order", 0),
                         1 if agent.get("is_lead") else 0, agent.get("weight", 1.0),
                         json.dumps(agent.get("conditions", None), ensure_ascii=False)),
                    )
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Squad {squad_id} updated successfully", "squad_id": squad_id}
    except Exception as e:
        return {"success": False, "error": _format_squad_error(e)}


def delete_squad(db_path: str | Path, squad_id: str) -> dict[str, Any]:
    """删除Squad。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT squad_id FROM squads WHERE squad_id = ?", (squad_id,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Squad {squad_id} not found"}
        cursor.execute("SELECT execution_id FROM squad_executions WHERE squad_id = ?", (squad_id,))
        exec_ids = [r["execution_id"] for r in cursor.fetchall()]
        for eid in exec_ids:
            cursor.execute("DELETE FROM squad_phase_executions WHERE execution_id = ?", (eid,))
        cursor.execute("DELETE FROM squad_executions WHERE squad_id = ?", (squad_id,))
        cursor.execute("DELETE FROM squad_workflows WHERE squad_id = ?", (squad_id,))
        cursor.execute("DELETE FROM squad_agents WHERE squad_id = ?", (squad_id,))
        cursor.execute("DELETE FROM squads WHERE squad_id = ?", (squad_id,))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Squad {squad_id} deleted successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_squads_batch(db_path: str | Path, squad_ids: list[str]) -> dict[str, Any]:
    """批量删除 Squad。"""
    deleted = 0
    for sid in squad_ids:
        result = delete_squad(db_path, sid)
        if result.get("success"):
            deleted += 1
    return {"success": True, "deleted": deleted}


def get_squad_executions(db_path: str | Path, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """获取Squad执行记录。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        query = ("SELECT e.*, s.name as squad_name, s.description as squad_description "
                 "FROM squad_executions e JOIN squads s ON e.squad_id = s.squad_id")
        params: list[Any] = []
        if status:
            query += " WHERE e.status = ?"
            params.append(status)
        query += " ORDER BY e.started_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        executions = []
        for row in cursor.fetchall():
            execution = dict(row)
            for jf in ["result_json", "metrics_json", "outputs_json"]:
                if execution.get(jf):
                    try:
                        execution[jf.replace("_json", "_data") if jf != "metrics_json" else "metrics"] = json.loads(execution[jf])
                    except Exception:
                        pass
            cursor.execute(
                "SELECT COUNT(*) as total_phases, SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_phases, "
                "AVG(duration_minutes) as avg_duration_minutes FROM squad_phase_executions WHERE execution_id = ?",
                (execution["execution_id"],),
            )
            ps = cursor.fetchone()
            if ps:
                execution["phase_stats"] = dict(ps)
            executions.append(execution)
        conn.close()
        return executions
    except Exception:
        return []


def get_squad_execution_detail(db_path: str | Path, execution_id: str) -> dict[str, Any]:
    """获取Squad执行详情。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT e.*, s.name as squad_name, s.description as squad_description "
            "FROM squad_executions e JOIN squads s ON e.squad_id = s.squad_id WHERE e.execution_id = ?",
            (execution_id,),
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"error": "Execution not found"}
        execution = dict(row)
        for jf in ["result_json", "metrics_json", "outputs_json"]:
            if execution.get(jf):
                try:
                    execution[jf.replace("_json", "_data") if jf != "metrics_json" else "metrics"] = json.loads(execution[jf])
                except Exception:
                    pass
        cursor.execute("SELECT * FROM squad_phase_executions WHERE execution_id = ? ORDER BY phase", (execution_id,))
        phases = []
        for pr in cursor.fetchall():
            phase = dict(pr)
            for jf in ["supporting_agents_json", "outputs_json", "success_criteria_met_json", "metrics_json"]:
                if phase.get(jf):
                    try:
                        phase[jf.replace("_json", "")] = json.loads(phase[jf])
                    except Exception:
                        pass
            phases.append(phase)
        execution["phases"] = phases
        conn.close()
        return execution
    except Exception as e:
        return {"error": str(e)}


def get_orchestration_patterns(db_path: str | Path) -> list[dict[str, Any]]:
    """获取所有编排模式。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orchestration_patterns WHERE is_active = 1 ORDER BY sort_order")
        patterns = []
        for row in cursor.fetchall():
            p = dict(row)
            for jf in ["default_phases_json", "flow_rules_json", "suitable_for_json"]:
                if p.get(jf):
                    try:
                        p[jf] = json.loads(p[jf])
                    except Exception:
                        p[jf] = []
            patterns.append(p)
        conn.close()
        return patterns
    except Exception:
        return []


def get_orchestration_pattern(db_path: str | Path, pattern_id: str) -> dict[str, Any]:
    """获取单个编排模式详情。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orchestration_patterns WHERE pattern_id = ?", (pattern_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            p = dict(row)
            for jf in ["default_phases_json", "flow_rules_json", "suitable_for_json"]:
                if p.get(jf):
                    try:
                        p[jf] = json.loads(p[jf])
                    except Exception:
                        p[jf] = []
            return p
        return {"error": "Pattern not found"}
    except Exception as e:
        return {"error": str(e)}


def _format_squad_error(e: Exception) -> str:
    err_msg = str(e)
    if "UNIQUE constraint failed: squad_workflows" in err_msg:
        return "阶段编号重复，请确保每个阶段的编号唯一"
    if "UNIQUE constraint failed: squad_agents" in err_msg:
        return "同一阶段内智能体名称重复"
    return err_msg


def _resolve_agent_repo(db_path: str | Path):
    """懒加载 AgentRepository。"""
    try:
        from infrastructure.persistence.agent_repo import AgentRepository
        from infrastructure.persistence.connection import SQLiteConnectionManager
        cm = SQLiteConnectionManager(str(db_path))
        repo = AgentRepository(cm)
        return repo
    except Exception:
        return None


def call_agent_for_squad(agent_name: str, task: str, context: dict) -> str:
    """调用单个智能体。
    """
    from interfaces.mcp.server import get_system
    system = get_system()
    if system:
        try:
            return system.agent_service.execute(agent_name, task, context)
        except Exception as e:
            return json.dumps({"agent": agent_name, "status": "error", "error": str(e)})
    return json.dumps({
        "agent": agent_name, "status": "simulated",
        "output": f"[模拟] {agent_name} 已处理: {task[:80]}", "type": "simulation",
    })


def _create_squad_contract(db_path: str | Path, agent_name: str, output: str,
                           phase_name: str, squad_name: str, next_agent: str | None = None) -> str | None:
    """为 squad 执行的 agent 输出创建契约，记录 agent 间通信。"""
    import uuid
    from datetime import datetime
    try:
        title = f"{agent_name} → {next_agent}" if next_agent else f"{agent_name}: {phase_name}"
        content = {
            "title": title,
            "description": f"Squad「{squad_name}」{phase_name} 阶段 {agent_name} 的输出",
            "source_agent": agent_name,
            "target_agent": next_agent or "",
            "phase": phase_name,
            "squad": squad_name,
            "output_summary": (output[:500] + '…') if isinstance(output, str) and len(output) > 500 else str(output)[:500],
        }
        contract_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO contracts (contract_id, contract_type, content_json, created_by, created_at, updated_at, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (contract_id, "api", json.dumps(content, ensure_ascii=False),
             f"squad:{squad_name}", now, now, "draft"),
        )
        conn.commit()
        conn.close()
        return contract_id
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# Squad 执行引擎
# ═══════════════════════════════════════════════════════════════════


def _get_lead_agent(phase_agents: list[dict[str, Any]]) -> str:
    """从阶段智能体列表中获取主智能体名称。"""
    if not phase_agents:
        return "unknown"
    leader = next(
        (a.get("agent_name", "") for a in phase_agents if a.get("is_lead")),
        phase_agents[0].get("agent_name", ""),
    )
    return leader or "unknown"


def _get_agent_names(phase_agents: list[dict[str, Any]]) -> list[str]:
    return [a.get("agent_name", "") for a in phase_agents if a.get("agent_name")]


def execute_squad_impl(db_path: str | Path, squad_id: str, execution_data: dict[str, Any]) -> dict[str, Any]:
    """执行Squad - 根据编排模式真实执行所有阶段。"""
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()
    start = __import__("time").time()
    trace_id, _ = db_log.trace("squad", "execute_start", f"squad={squad_id}",
                               {"squad_id": squad_id, "trigger": execution_data.get("trigger_type", "manual")})

    conn = None
    try:
        conn = _connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM squads WHERE squad_id = ?", (squad_id,))
        squad_row = cursor.fetchone()
        if not squad_row:
            conn.close()
            return {"success": False, "error": f"Squad {squad_id} not found"}
        squad = dict(squad_row)
        workflow_type = squad.get("workflow_type", "sequential")

        execution_id = f"exec-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{squad_id}"

        cursor.execute("SELECT * FROM squad_workflows WHERE squad_id = ? ORDER BY phase", (squad_id,))
        workflow_rows = cursor.fetchall()
        if not workflow_rows:
            conn.close()
            return {"success": False, "error": f"Squad {squad_id} has no workflows"}
        workflows = []
        for row in workflow_rows:
            wf = dict(row)
            if wf.get("conditions_json") and isinstance(wf["conditions_json"], str):
                try:
                    wf["conditions_json"] = json.loads(wf["conditions_json"])
                except Exception:
                    pass
            workflows.append(wf)

        cursor.execute("SELECT * FROM squad_agents WHERE squad_id = ? ORDER BY phase, sort_order", (squad_id,))
        agent_rows = cursor.fetchall()
        agents = []
        for row in agent_rows:
            agent = dict(row)
            if agent.get("conditions_json") and isinstance(agent["conditions_json"], str):
                try:
                    agent["conditions_json"] = json.loads(agent["conditions_json"])
                except Exception:
                    pass
            agents.append(agent)

        agents_by_phase: dict[int, list] = {}
        for agent in agents:
            agents_by_phase.setdefault(agent.get("phase", 1), []).append(agent)

        total_phases = len(workflows)
        cursor.execute(
            "INSERT INTO squad_executions (execution_id, squad_id, name, description, status, current_phase, progress_percent, started_at, created_by, result_json, outputs_json, metrics_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                execution_id, squad_id,
                f"执行: {squad.get('name', 'Squad')}",
                execution_data.get("description", f"执行Squad {squad_id}"),
                "running", 1, 0.0, datetime.now().isoformat(),
                execution_data.get("created_by", "system"),
                json.dumps({"trigger_type": execution_data.get("trigger_type", "manual"), "trigger_by": execution_data.get("trigger_by", "system"), "input_params": execution_data.get("input_params", {})}),
                json.dumps({}),
                json.dumps({"total_phases": total_phases, "completed_phases": 0, "success_rate": 0.0}),
            ),
        )

        phase_context = {
            "squad_name": squad.get("name", ""),
            "squad_description": squad.get("description", ""),
            "input_params": execution_data.get("input_params", {}),
            "previous_phase_output": "",
            "all_phase_outputs": {},
            "_db_path": str(db_path),
        }

        completed_phases = 0
        failed_phases = 0
        all_phase_outputs: dict[str, Any] = {}

        if workflow_type == "parallel":
            phase_record_map = {}
            for wf in workflows:
                pn = wf["phase"]
                phase_agent_list = agents_by_phase.get(pn, [])
                lead_agent = _get_lead_agent(phase_agent_list)
                agent_names = _get_agent_names(phase_agent_list)
                cursor.execute(
                    "INSERT INTO squad_phase_executions (execution_id, phase, phase_name, status, primary_agent, supporting_agents_json, started_at, outputs_json, success_criteria_met_json, metrics_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (execution_id, pn, wf.get("name", f"阶段 {pn}"), "running", lead_agent,
                     json.dumps(agent_names), datetime.now().isoformat(), json.dumps({}), json.dumps([]),
                     json.dumps({"mode": wf.get("mode", "sequential")})),
                )
                phase_record_map[pn] = True
            conn.commit()

            phase_results: dict[int, Any] = {}
            with ThreadPoolExecutor(max_workers=max(total_phases, 1)) as executor:
                future_map = {
                    executor.submit(
                        _execute_single_phase, db_path, wf, agents_by_phase.get(wf["phase"], []),
                        wf.get("mode", "sequential"), dict(phase_context), squad_id, execution_id,
                        trace_id
                    ): wf["phase"]
                    for wf in workflows
                }
                for future in as_completed(future_map):
                    pn = future_map[future]
                    try:
                        phase_results[pn] = future.result(timeout=600)
                        completed_phases += 1
                    except Exception as e:
                        phase_results[pn] = {"phase": pn, "status": "failed", "outputs": {"error": str(e)}}
                        failed_phases += 1

            for pn, result in phase_results.items():
                cursor.execute(
                    "UPDATE squad_phase_executions SET status=?, outputs_json=?, metrics_json=? WHERE execution_id=? AND phase=?",
                    (result.get("status", "failed"), json.dumps(result.get("outputs", {})),
                     json.dumps({"mode": "parallel", "duration_minutes": result.get("duration_minutes", 0)}),
                     execution_id, pn)
                )
                all_phase_outputs[f"phase_{pn}"] = result.get("outputs", {})

            cursor.execute(
                "UPDATE squad_executions SET current_phase=?, progress_percent=100.0, metrics_json=? WHERE execution_id=?",
                (total_phases, json.dumps({"total_phases": total_phases, "completed_phases": completed_phases, "failed_phases": failed_phases, "workflow_type": "parallel"}), execution_id)
            )
        else:
            for phase_idx, wf in enumerate(workflows):
                phase_num = wf["phase"]
                phase_mode = wf.get("mode", "sequential")
                phase_agents = agents_by_phase.get(phase_num, [])

                cursor.execute(
                    "UPDATE squad_executions SET current_phase=? WHERE execution_id=?", (phase_num, execution_id)
                )

                lead_agent = _get_lead_agent(phase_agents)
                agent_names = _get_agent_names(phase_agents)
                cursor.execute(
                    "INSERT INTO squad_phase_executions (execution_id, phase, phase_name, status, primary_agent, supporting_agents_json, started_at, outputs_json, success_criteria_met_json, metrics_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (execution_id, phase_num, wf.get("name", f"阶段 {phase_num}"), "running", lead_agent,
                     json.dumps(agent_names), datetime.now().isoformat(), json.dumps({}), json.dumps([]),
                     json.dumps({"mode": phase_mode})),
                )
                conn.commit()

                try:
                    result = _execute_single_phase(
                        db_path, wf, phase_agents, phase_mode, phase_context, squad_id, execution_id,
                        trace_id=trace_id,
                    )
                    phase_status = result.get("status", "failed")
                    phase_outputs = result.get("outputs", {})
                except Exception as e:
                    phase_status = "failed"
                    phase_outputs = {"error": str(e)}

                cursor.execute(
                    "UPDATE squad_phase_executions SET status=?, outputs_json=?, metrics_json=? WHERE execution_id=? AND phase=?",
                    (phase_status, json.dumps(phase_outputs),
                     json.dumps({"mode": phase_mode, "duration_minutes": result.get("duration_minutes", 0) if 'result' in dir() else 0}),
                     execution_id, phase_num)
                )

                if phase_status == "completed":
                    completed_phases += 1
                else:
                    failed_phases += 1

                phase_context["previous_phase_output"] = phase_outputs
                all_phase_outputs[f"phase_{phase_num}"] = phase_outputs

                progress = ((phase_idx + 1) / total_phases) * 100
                cursor.execute(
                    "UPDATE squad_executions SET progress_percent=?, metrics_json=? WHERE execution_id=?",
                    (progress, json.dumps({"total_phases": total_phases, "completed_phases": completed_phases, "failed_phases": failed_phases, "workflow_type": workflow_type}), execution_id)
                )

        final_status = "completed" if failed_phases == 0 else "completed_with_errors"
        overall_success = failed_phases == 0

        cursor.execute(
            "UPDATE squad_executions SET status=?, completed_at=CURRENT_TIMESTAMP, progress_percent=100.0, result_json=?, outputs_json=?, metrics_json=? WHERE execution_id=?",
            (
                final_status,
                json.dumps({"final_status": "success" if overall_success else "partial", "message": f"Squad {squad_id} 执行{'完成' if overall_success else '完成（部分失败）'}", "workflow_type": workflow_type, "total_phases": total_phases, "completed_phases": completed_phases, "failed_phases": failed_phases}),
                json.dumps(all_phase_outputs),
                json.dumps({"total_phases": total_phases, "completed_phases": completed_phases, "failed_phases": failed_phases, "workflow_type": workflow_type, "success_rate": (completed_phases / total_phases) * 100 if total_phases > 0 else 0}),
                execution_id,
            ),
        )

        cursor.execute(
            "UPDATE squads SET execution_count=execution_count+1, success_count=success_count+?, last_executed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE squad_id=?",
            (1 if overall_success else 0, squad_id)
        )

        conn.commit()
        conn.close()

        elapsed = int((__import__("time").time() - start) * 1000)
        db_log.log("INFO", "squad", "execute_complete", f"squad={squad_id}, status={final_status}",
                   trace_id=trace_id, duration_ms=elapsed,
                   metadata={"squad_id": squad_id, "execution_id": execution_id, "status": final_status,
                             "total_phases": total_phases, "completed_phases": completed_phases, "failed_phases": failed_phases})
        return {
            "success": True, "message": f"Squad {squad_id} 执行完成", "execution_id": execution_id,
            "squad_id": squad_id, "status": final_status, "total_phases": total_phases,
            "completed_phases": completed_phases, "failed_phases": failed_phases, "workflow_type": workflow_type,
        }
    except Exception as e:
        elapsed = int((__import__("time").time() - start) * 1000)
        db_log.log("ERROR", "squad", "execute_failed", f"squad={squad_id}, err={str(e)[:200]}",
                   trace_id=trace_id, duration_ms=elapsed,
                   metadata={"squad_id": squad_id, "error": str(e)[:500]})
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
        return {"success": False, "error": str(e)}


def _execute_single_phase(
    db_path: str | Path, wf: dict, phase_agents: list, phase_mode: str,
    phase_context: dict, squad_id: str, execution_id: str,
    trace_id: str | None = None,
) -> dict:
    """执行单个阶段。"""
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()
    phase_start = __import__("time").time()

    phase_name = wf.get("name", "")
    phase_num = wf.get("phase", 0)
    task = wf.get("description", f"执行{phase_name if phase_name else '阶段 ' + str(phase_num)}")
    # 注入用户原始需求到任务描述
    user_task = phase_context.get("input_params", {}).get("task", "")
    if user_task:
        task = f"【用户需求】\n{user_task}\n\n【当前阶段任务】\n{task}"

    # 注入前序阶段的契约产出，使当前阶段智能体能感知已完成的工作
    contract_ids = phase_context.get("_contract_ids", [])
    if contract_ids:
        try:
            db_conn = _connect(db_path)
            placeholders = ",".join("?" for _ in contract_ids)
            rows = db_conn.execute(
                f"SELECT content_json FROM contracts WHERE contract_id IN ({placeholders})",
                contract_ids,
            ).fetchall()
            db_conn.close()
            summaries = []
            for row in rows:
                c = json.loads(row["content_json"]) if isinstance(row["content_json"], str) else row["content_json"]
                title = c.get("title", c.get("name", "契约"))
                summary = c.get("output_summary", "")
                if summary:
                    summaries.append(f"  - {title}: {summary[:200]}")
            if summaries:
                task += f"\n\n【已完成的前序阶段产出】\n" + "\n".join(summaries)
        except Exception:
            pass  # 契约注入失败不影响执行

    db_log.log("INFO", "squad", "phase_start", f"phase={phase_num}, mode={phase_mode}, agents={len(phase_agents)}",
               metadata={"squad_id": squad_id, "execution_id": execution_id, "phase": phase_num, "mode": phase_mode},
               trace_id=trace_id)

    start_time = datetime.now()
    db = None
    try:
        # 注入 trace_id 到 phase_context，供 LLM 调用日志复用同一链路
        if trace_id:
            phase_context["trace_id"] = trace_id
        handlers = {
            "sequential": _execute_phase_sequential,
            "parallel": _execute_phase_parallel,
            "conditional": _execute_phase_conditional,
            "hierarchical": lambda w, a, t, c: _execute_phase_hierarchical(db_path, w, a, t, c, squad_id),
            "consensus": _execute_phase_consensus,
        }
        handler = handlers.get(phase_mode, _execute_phase_sequential)
        results = handler(wf, phase_agents, task, phase_context)

        end_time = datetime.now()
        duration_min = round((end_time - start_time).total_seconds() / 60.0, 2)

        outputs: dict[str, Any] = {}
        agent_log: list[dict] = []
        errors: list[dict] = []
        for r in results:
            key = r.get("agent", r.get("sub_squad", "unknown"))
            raw = r.get("output", "")
            outputs[key] = raw
            summary = (raw[:200] + "...") if isinstance(raw, str) and len(raw) > 200 else raw
            agent_log.append({"agent": key, "status": r.get("status", "unknown"), "summary": summary})
            if r.get("status") == "failed":
                errors.append({"agent": key, "error": (raw[:500] if isinstance(raw, str) else str(raw)[:500])})

        db = _connect(db_path)
        status = "completed" if not errors else "completed_with_errors"
        db.execute(
            "UPDATE squad_phase_executions SET status=?, completed_at=?, duration_minutes=?, outputs_json=?, metrics_json=?, error_message=?, error_details_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=? AND phase=?",
            (
                status, end_time.isoformat(), duration_min,
                json.dumps(outputs, ensure_ascii=False),
                json.dumps({"mode": phase_mode, "duration_minutes": duration_min, "total_agents": len(results), "failed_agents": len(errors), "agent_log": agent_log}, ensure_ascii=False),
                errors[0]["error"] if errors else None,
                json.dumps(errors, ensure_ascii=False) if errors else None,
                execution_id, phase_num,
            ),
        )
        db.commit()
        db.close()

        phase_elapsed = int((__import__("time").time() - phase_start) * 1000)
        db_log.log("INFO", "squad", "phase_complete", f"phase={phase_num}, status={status}",
                   metadata={"squad_id": squad_id, "execution_id": execution_id, "phase": phase_num,
                             "status": status, "duration_ms": phase_elapsed},
                   trace_id=trace_id)
        return {
            "phase": phase_num, "status": status, "outputs": outputs, "results": results,
            "duration_minutes": duration_min,
        }
    except Exception as e:
        end_time = datetime.now()
        duration_min = round((end_time - start_time).total_seconds() / 60.0, 2)
        phase_elapsed = int((__import__("time").time() - phase_start) * 1000)
        db_log.log("ERROR", "squad", "phase_failed", f"phase={phase_num}, err={str(e)[:200]}",
                   metadata={"squad_id": squad_id, "execution_id": execution_id, "phase": phase_num,
                             "error": str(e)[:500], "duration_ms": phase_elapsed},
                   trace_id=trace_id)
        try:
            if db is None:
                db = _connect(db_path)
            db.execute(
                "UPDATE squad_phase_executions SET status='failed', completed_at=?, duration_minutes=?, error_message=?, error_details_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=? AND phase=?",
                (end_time.isoformat(), duration_min, str(e)[:500],
                 json.dumps({"error": str(e), "mode": phase_mode}, ensure_ascii=False), execution_id, phase_num),
            )
            db.commit()
        except Exception:
            pass
        finally:
            if db:
                try:
                    db.close()
                except Exception:
                    pass
        return {
            "phase": phase_num, "status": "failed", "outputs": {"error": str(e)}, "results": [],
            "duration_minutes": duration_min,
        }


def _execute_phase_sequential(wf: dict, agents: list, task: str, context: dict) -> list:
    """串行模式：智能体逐个执行，并在每次调用后创建通信契约。"""
    results = []
    for i, a in enumerate(agents):
        name = a.get("agent_name", "")
        if not name:
            continue
        ctx = {**context, "phase_name": wf.get("name", "")}
        output = call_agent_for_squad(name, task, ctx)
        results.append({"agent": name, "output": output, "status": "completed"})
        context["previous_agent_output"] = output
        # 创建契约记录 agent 间通信（最后一个 agent 指向下一阶段）
        next_name = agents[i + 1].get("agent_name", "") if i + 1 < len(agents) else "下一阶段"
        db_path = context.get("_db_path")
        if db_path:
            try:
                cid = _create_squad_contract(
                    db_path, name, output,
                    wf.get("name", ""),
                    context.get("squad_name", ""),
                    next_name,
                )
                if cid:
                    context.setdefault("_contract_ids", []).append(cid)
                    ctx["_contract_ids"] = context.get("_contract_ids", [])
            except Exception:
                pass  # 契约创建失败不影响执行
        # 积累 token 用量到共享 context
        context.setdefault("_phase_token_input", 0)
        context.setdefault("_phase_token_output", 0)
        context["_phase_token_input"] += ctx.get("_token_input", 0)
        context["_phase_token_output"] += ctx.get("_token_output", 0)
        if ctx.get("_token_model"):
            context["_phase_token_model"] = ctx["_token_model"]
        if ctx.get("_token_used"):
            context.setdefault("_phase_token_used", 0)
            context["_phase_token_used"] += ctx["_token_used"]
    return results


def _execute_phase_parallel(wf: dict, agents: list, task: str, context: dict) -> list:
    """并行模式：所有智能体并发执行。"""
    if not agents:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=len(agents)) as exe:
        fm = {exe.submit(call_agent_for_squad, a.get("agent_name", ""), task, {**context, "phase_name": wf.get("name", "")}): a.get("agent_name", "") for a in agents if a.get("agent_name")}
        for f in as_completed(fm):
            name = fm[f]
            try:
                results.append({"agent": name, "output": f.result(timeout=300), "status": "completed"})
            except Exception as e:
                results.append({"agent": name, "output": f"[错误] {e}", "status": "failed"})
    return results


def _execute_phase_conditional(wf: dict, agents: list, task: str, context: dict) -> list:
    """条件分支模式。"""
    prev = context.get("previous_phase_output", "")
    prev_str = str(prev) if not isinstance(prev, str) else prev
    if isinstance(prev, dict):
        prev_str = json.dumps(prev, ensure_ascii=False)
    results = []
    for a in agents:
        name = a.get("agent_name", "")
        if not name:
            continue
        conditions = a.get("conditions_json")
        if conditions:
            matched = False
            for cond in conditions if isinstance(conditions, list) else []:
                kw = cond.get("keyword", "")
                if kw and kw in prev_str:
                    matched = True
                    break
            if not matched:
                continue
        ctx = {**context, "phase_name": wf.get("name", "")}
        output = call_agent_for_squad(name, task, ctx)
        results.append({"agent": name, "output": output, "status": "completed"})
    return results


def _execute_phase_hierarchical(
    db_path: str | Path, wf: dict, agents: list, task: str, context: dict, squad_id: str
) -> list:
    """层次模式：递归执行子Squad。"""
    sub_squads = []
    try:
        c2 = _connect(db_path)
        c2.row_factory = sqlite3.Row
        rows = c2.execute("SELECT squad_id, name FROM squads WHERE parent_squad_id=?", (squad_id,)).fetchall()
        sub_squads = [dict(r) for r in rows]
        c2.close()
    except Exception:
        pass
    if sub_squads:
        results = []
        for sub in sub_squads:
            sub_r = execute_squad_impl(
                db_path, sub["squad_id"], {
                    "trigger_by": f"squad:{squad_id}",
                    "description": f"子Squad: {sub['name']}",
                    "input_params": {"parent_context": context, "task": task},
                }
            )
            results.append({
                "sub_squad": sub["squad_id"], "sub_squad_name": sub["name"],
                "output": json.dumps(sub_r, ensure_ascii=False),
                "status": "completed" if sub_r.get("success") else "failed",
            })
        return results
    return _execute_phase_sequential(wf, agents, f"{task} [无子Squad]", context)


def _execute_phase_consensus(wf: dict, agents: list, task: str, context: dict) -> list:
    """共识模式：多智能体独立执行后投票取共识。"""
    if not agents:
        return []
    individual: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=len(agents)) as exe:
        fm = {exe.submit(call_agent_for_squad, a.get("agent_name", ""), task, {**context, "phase_name": wf.get("name", ""), "consensus_round": True}): a.get("agent_name", "") for a in agents if a.get("agent_name")}
        for f in as_completed(fm):
            name = fm[f]
            try:
                individual[name] = f.result(timeout=300)
            except Exception as e:
                individual[name] = f"[错误] {e}"

    consensus = _perform_consensus(individual)
    results = [{"agent": n, "output": o, "status": "completed", "consensus_round": True} for n, o in individual.items()]
    results.append({
        "agent": "__consensus__", "output": json.dumps(consensus, ensure_ascii=False), "status": "consensus",
        "is_consensus": True,
    })
    return results


def _perform_consensus(individual: dict) -> dict:
    """共识聚合：多数投票。"""
    if not individual:
        return {"decision": "无结果", "agreement": 0, "total_agents": 0}
    n = len(individual)
    parsed: dict[str, Any] = {}
    for agent, output in individual.items():
        try:
            parsed[agent] = json.loads(output) if isinstance(output, str) else output
        except (json.JSONDecodeError, TypeError):
            parsed[agent] = {"text": str(output)[:100]}
    types_list = [r.get("type", "unknown") for r in parsed.values() if isinstance(r, dict)]
    if types_list:
        top_type, top_count = Counter(types_list).most_common(1)[0]
        agreement = round(top_count / n, 2)
    else:
        top_type = "text"
        agreement = 1.0
    return {
        "decision": f"共识决策: {top_type}", "agreement": agreement, "total_agents": n,
        "agreeing_count": int(agreement * n),
        "details": {a: r.get("type", "unknown") for a, r in parsed.items()},
    }


# ═══════════════════════════════════════════════════════════════════
# HITL (Human-in-the-Loop) Squad 执行
# ═══════════════════════════════════════════════════════════════════


def execute_squad_hitl(db_path: str | Path, squad_id: str, execution_data: dict[str, Any],
                       extra_context: dict | None = None) -> dict[str, Any]:
    """HITL 模式启动 Squad 执行：运行第一个 phase 后暂停等待用户确认。"""
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()
    start = __import__("time").time()
    # 优先复用调用方传入的 trace_id，保持全流程统一
    existing_trace = (extra_context or {}).get("trace_id", "")
    if existing_trace:
        trace_id = existing_trace
    else:
        trace_id, _ = db_log.trace("squad", "hitl_start", f"squad={squad_id}",
                                   {"squad_id": squad_id, "hitl": True})

    try:
        conn = _connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM squads WHERE squad_id=?", (squad_id,))
        squad_row = cursor.fetchone()
        if not squad_row:
            conn.close()
            return {"success": False, "error": "Squad not found"}
        squad = dict(squad_row)

        cursor.execute("SELECT * FROM squad_workflows WHERE squad_id=? ORDER BY phase", (squad_id,))
        workflows = []
        for row in cursor.fetchall():
            wf = dict(row)
            if wf.get("conditions_json") and isinstance(wf["conditions_json"], str):
                try:
                    wf["conditions_json"] = json.loads(wf["conditions_json"])
                except Exception:
                    pass
            workflows.append(wf)

        cursor.execute("SELECT * FROM squad_agents WHERE squad_id=? ORDER BY phase, sort_order", (squad_id,))
        agents_by_phase: dict[int, list] = {}
        for row in cursor.fetchall():
            agent = dict(row)
            if agent.get("conditions_json") and isinstance(agent["conditions_json"], str):
                try:
                    agent["conditions_json"] = json.loads(agent["conditions_json"])
                except Exception:
                    pass
            agents_by_phase.setdefault(agent.get("phase", 1), []).append(agent)

        total_phases = len(workflows)
        execution_id = f"exec-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{squad_id}"

        cursor.execute(
            "INSERT INTO squad_executions (execution_id, squad_id, name, description, status, current_phase, progress_percent, started_at, created_by, result_json, outputs_json, metrics_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (execution_id, squad_id, f"执行: {squad.get('name', 'Squad')}",
             execution_data.get("description", ""), "running", 1, 0.0,
             datetime.now().isoformat(), execution_data.get("created_by", "system"),
             json.dumps({"type": "hitl_active", "phase_index": 0, "trace_id": trace_id}, ensure_ascii=False),
             json.dumps({}), json.dumps({"total_phases": total_phases, "hitl": True})),
        )

        phase_context = {
            "squad_name": squad.get("name", ""),
            "squad_description": squad.get("description", ""),
            "input_params": execution_data.get("input_params", {}),
            "previous_phase_output": "",
        }

        # Run first phase
        phase_result = _run_hitl_phase(
            db_path, conn, cursor, execution_id, workflows, agents_by_phase,
            phase_idx=0, phase_context=phase_context, correction_text=None,
            trace_id=trace_id, extra_context=extra_context,
        )

        conn.commit()
        conn.close()

        elapsed = int((__import__("time").time() - start) * 1000)
        db_log.log("INFO", "squad", "hitl_pause", f"squad={squad_id}, phase={phase_result['phase_num']}",
                   trace_id=trace_id, duration_ms=elapsed,
                   metadata={"execution_id": execution_id, "phase": phase_result["phase_num"],
                             "status": phase_result["status"]})

        hitl_waiting = phase_result.get("next_status", "paused") == "paused"
        return {
            "success": True,
            "execution_id": execution_id,
            "squad_id": squad_id,
            "status": "paused" if hitl_waiting else phase_result["status"],
            "current_phase": phase_result["phase_num"],
            "current_phase_name": phase_result["phase_name"],
            "total_phases": total_phases,
            "completed_phases": phase_result["completed_phases"],
            "failed_phases": phase_result["failed_phases"],
            "current_phase_output": phase_result["outputs"],
            "phase_status": phase_result["status"],
            "hitl_waiting": hitl_waiting,
            "trace_id": trace_id,
            "token_input": phase_result.get("token_input", 0),
            "token_output": phase_result.get("token_output", 0),
            "token_used": phase_result.get("token_used", 0),
            "token_model": phase_result.get("token_model", ""),
        }
    except Exception as e:
        elapsed = int((__import__("time").time() - start) * 1000)
        db_log.log("ERROR", "squad", "hitl_failed", f"squad={squad_id}, err={str(e)[:200]}",
                   trace_id=trace_id, duration_ms=elapsed)
        return {"success": False, "error": str(e)}


def advance_squad_execution(
    db_path: str | Path,
    execution_id: str,
    action: str,
    correction_text: str | None = None,
    extra_context: dict | None = None,
) -> dict[str, Any]:
    """推进 HITL 暂停的执行：继续 / 修正后继续 / 中止。"""
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()
    start = __import__("time").time()

    try:
        conn = _connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM squad_executions WHERE execution_id=?",
            (execution_id,),
        )
        exec_row = cursor.fetchone()
        if not exec_row:
            conn.close()
            return {"success": False, "error": "Execution not found"}
        execution = dict(exec_row)
        if execution.get("status") != "paused":
            conn.close()
            return {"success": False, "error": "Execution is not in paused state"}

        hitl_state = json.loads(execution.get("result_json") or "{}")
        if hitl_state.get("type") != "hitl_paused":
            conn.close()
            return {"success": False, "error": "Invalid HITL state"}

        squad_id = execution["squad_id"]
        # 从 HITL 状态中取首次启动时生成的 trace_id，保持全流程统一
        trace_id = hitl_state.get("trace_id")
        if not trace_id:
            trace_id, _ = db_log.trace("squad", "hitl_advance", f"exec={execution_id[:12]}, action={action}",
                                       metadata={"execution_id": execution_id, "action": action})

        db_log.log("INFO", "squad", "hitl_advance", f"exec={execution_id[:12]}, action={action}",
                   trace_id=trace_id, metadata={"execution_id": execution_id, "action": action})

        if action == "abort":
            all_outputs = json.loads(execution.get("outputs_json") or "{}")
            cursor.execute(
                "UPDATE squad_executions SET status='aborted', completed_at=CURRENT_TIMESTAMP, progress_percent=100.0, outputs_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=?",
                (json.dumps(all_outputs, ensure_ascii=False), execution_id),
            )
            conn.commit()
            conn.close()
            db_log.log("INFO", "squad", "hitl_aborted", f"exec={execution_id[:12]}",
                       trace_id=trace_id, metadata={"execution_id": execution_id})
            return {"success": True, "status": "aborted", "execution_id": execution_id}

        # continue / correct — reload squad data and run next phase
        cursor.execute("SELECT * FROM squad_workflows WHERE squad_id=? ORDER BY phase", (squad_id,))
        workflows = []
        for row in cursor.fetchall():
            wf = dict(row)
            if wf.get("conditions_json") and isinstance(wf["conditions_json"], str):
                try:
                    wf["conditions_json"] = json.loads(wf["conditions_json"])
                except Exception:
                    pass
            workflows.append(wf)

        cursor.execute("SELECT * FROM squad_agents WHERE squad_id=? ORDER BY phase, sort_order", (squad_id,))
        agents_by_phase: dict[int, list] = {}
        for row in cursor.fetchall():
            agent = dict(row)
            if agent.get("conditions_json") and isinstance(agent["conditions_json"], str):
                try:
                    agent["conditions_json"] = json.loads(agent["conditions_json"])
                except Exception:
                    pass
            agents_by_phase.setdefault(agent.get("phase", 1), []).append(agent)

        phase_idx = hitl_state.get("phase_index", 0) + 1
        phase_context = hitl_state.get("phase_context", {})
        all_phase_outputs = hitl_state.get("all_phase_outputs", {})
        completed_phases = hitl_state.get("completed_phases", 0)
        failed_phases = hitl_state.get("failed_phases", 0)

        # If correction, inject into context
        if action == "correct" and correction_text:
            if "corrections" not in phase_context:
                phase_context["corrections"] = []
            phase_context["corrections"].append({
                "phase_index": phase_idx,
                "text": correction_text,
            })
            phase_context["previous_phase_output"] = correction_text

        if phase_idx >= len(workflows):
            # All phases done — mark complete
            status = "completed" if failed_phases == 0 else "completed_with_errors"
            cursor.execute(
                "UPDATE squad_executions SET status=?, completed_at=CURRENT_TIMESTAMP, progress_percent=100.0, result_json=?, outputs_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=?",
                (status, json.dumps({"type": "hitl_complete", "completed_phases": completed_phases, "failed_phases": failed_phases}, ensure_ascii=False),
                 json.dumps(all_phase_outputs, ensure_ascii=False), execution_id),
            )
            conn.commit()
            conn.close()
            db_log.log("INFO", "squad", "hitl_complete", f"exec={execution_id[:12]}, status={status}",
                       trace_id=trace_id, metadata={"execution_id": execution_id, "status": status})
            return {
                "success": True,
                "status": status,
                "execution_id": execution_id,
                "total_phases": len(workflows),
                "completed_phases": completed_phases,
                "failed_phases": failed_phases,
                "hitl_complete": True,
                "all_phase_outputs": all_phase_outputs,
            }

        # Run next phase
        phase_result = _run_hitl_phase(
            db_path, conn, cursor, execution_id, workflows, agents_by_phase,
            phase_idx=phase_idx, phase_context=phase_context,
            correction_text=correction_text if action == "correct" else None,
            all_phase_outputs_so_far=all_phase_outputs,
            trace_id=trace_id, extra_context=extra_context,
        )

        conn.commit()
        conn.close()

        total_phases = len(workflows)
        is_last = phase_idx >= total_phases - 1
        returned_status = phase_result.get("next_status", "paused" if not is_last else "completed")

        db_log.log("INFO", "squad", "hitl_advance_done", f"exec={execution_id[:12]}, phase={phase_result['phase_num']}, status={returned_status}",
                   trace_id=trace_id, metadata={"execution_id": execution_id, "phase": phase_result["phase_num"], "status": returned_status})

        is_complete = returned_status != "paused"
        phase_duration_ms = int(phase_result.get("duration_minutes", 0) * 60 * 1000)
        token_input = phase_result.get("token_input", 0)
        token_output = phase_result.get("token_output", 0)
        token_used = phase_result.get("token_used", 0)
        token_model = phase_result.get("token_model", "")
        return {
            "success": True,
            "execution_id": execution_id,
            "status": returned_status,
            "current_phase": phase_result.get("phase_num"),
            "current_phase_name": phase_result.get("phase_name"),
            "total_phases": total_phases,
            "completed_phases": completed_phases + phase_result.get("completed_phases", 0),
            "failed_phases": failed_phases + phase_result.get("failed_phases", 0),
            "current_phase_output": phase_result.get("outputs", {}),
            "all_phase_outputs": phase_result.get("all_outputs", {}),
            "phase_status": phase_result.get("status"),
            "elapsed_ms": phase_duration_ms,
            "token_input": token_input,
            "token_output": token_output,
            "token_used": token_used,
            "token_model": token_model,
            "hitl_waiting": not is_complete,
            "hitl_complete": is_complete,
        }
    except Exception as e:
        db_log.log("ERROR", "squad", "hitl_advance_failed", f"exec={execution_id[:12]}, err={str(e)[:200]}",
                   metadata={"execution_id": execution_id, "error": str(e)[:500]})
        return {"success": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════
# 动态 Squad 执行（元编排器用）
# ═══════════════════════════════════════════════════════════════════


def execute_dynamic_squad(
    db_path: str | Path,
    topology: dict[str, Any],
    task_description: str = "",
    extra_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据动态拓扑执行编排，不依赖预设 squad_id。

    元编排器生成拓扑后，直接传入执行，无需提前创建 squad 记录。

    Args:
        db_path: 数据库路径
        topology: 编排拓扑 dict
            {"phases": [{"phase": 1, "mode":"sequential", "agents":[..], "description":"..."}], "mode": "..."}
        task_description: 原始用户任务描述
        extra_context: 额外上下文（如 stream_callback、trace_id）

    Returns:
        dict: 执行结果，包含各阶段输出
    """
    from infrastructure.logging.db_logger import get_db_logger
    db_log = get_db_logger()
    start_time = __import__("time").time()
    trace_id = (extra_context or {}).get("trace_id", "")
    if not trace_id:
        trace_id, _ = db_log.trace("squad", "dynamic_exec_start", "动态Squad执行",
                                   metadata={"task_preview": task_description[:100]})

    phases = topology.get("phases", [])
    if not phases:
        return {"success": False, "error": "拓扑中没有定义阶段", "outputs": {}}

    # 将 LLM 生成的拓扑 agent 名称向真实注册表解析
    try:
        from application.services.agent_resolver import AgentResolver
        resolver = AgentResolver(db_path)
        resolved = resolver.resolve_topology(topology, task_context=task_description)
        phases = resolved.get("phases", [])
        topology = resolved

        # 新创建的 agent 只写入了 DB 和 AgentResolver 私有缓存，
        # 但 call_agent_for_squad 使用的是全局 SystemContext.agent_service，
        # 两者是不同的 AgentRepository 实例，必须同步过去。
        # orchestrator 始终在全局缓存中，不需要同步。
        try:
            from interfaces.mcp.server import get_system
            system = get_system()
            for phase_def in phases:
                for aid in phase_def.get("agents", []):
                    if aid == "orchestrator":
                        continue
                    ok = system.agent_service.reload(aid)
                    if not ok:
                        logger.warning("execute_dynamic_squad: agent '%s' 同步到全局缓存失败（DB 中不存在）", aid)
        except Exception as sync_exc:
            logger.warning("同步新 agent 到全局缓存失败: %s", sync_exc)
    except Exception as exc:
        logger.warning("AgentResolver 解析失败，使用原始拓扑: %s", exc)
        topology = topology  # 保持原样，兼容执行

    phase_context: dict[str, Any] = {
        "squad_name": "动态编排",
        "squad_description": "元编排器动态生成的编排",
        "input_params": {"task": task_description},
        "previous_phase_output": "",
        "all_phase_outputs": {},
        "_db_path": str(db_path),
    }
    if extra_context:
        phase_context.update(extra_context)
    if trace_id:
        phase_context["trace_id"] = trace_id

    all_outputs: dict[str, Any] = {}
    completed_phases = 0
    failed_phases = 0

    for phase_def in phases:
        phase_num = phase_def.get("phase", 1)
        phase_mode = phase_def.get("mode", "sequential")
        agent_names = phase_def.get("agents", [])
        phase_desc = phase_def.get("description", f"阶段 {phase_num}")

        # 构建 wf 和 phase_agents 格式（与 execute_squad_impl 兼容）
        wf = {
            "phase": phase_num,
            "name": f"阶段 {phase_num}",
            "description": phase_desc,
            "mode": phase_mode,
        }
        phase_agents = [{"agent_name": name, "is_lead": i == 0}
                        for i, name in enumerate(agent_names)]

        try:
            result = _execute_single_phase(
                db_path, wf, phase_agents, phase_mode, phase_context,
                squad_id="dynamic", execution_id=f"dynamic-{int(start_time)}",
                trace_id=trace_id,
            )
            phase_status = result.get("status", "failed")
        except Exception as e:
            phase_status = "failed"
            result = {"outputs": {"error": str(e)}}

        if phase_status == "completed":
            completed_phases += 1
        else:
            failed_phases += 1

        phase_context["previous_phase_output"] = result.get("outputs", {})
        all_outputs[f"phase_{phase_num}"] = result.get("outputs", {})

    final_status = "completed" if failed_phases == 0 else "completed_with_errors"
    elapsed_ms = int((__import__("time").time() - start_time) * 1000)

    db_log.log("INFO", "squad", "dynamic_exec_complete",
               f"phases={len(phases)}, status={final_status}",
               trace_id=trace_id, duration_ms=elapsed_ms,
               metadata={"total_phases": len(phases), "completed": completed_phases,
                         "failed": failed_phases, "dynamic": True})

    return {
        "success": failed_phases == 0,
        "status": final_status,
        "phases": phases,
        "outputs": all_outputs,
        "completed_phases": completed_phases,
        "failed_phases": failed_phases,
        "total_phases": len(phases),
        "elapsed_ms": elapsed_ms,
    }


def _run_hitl_phase(
    db_path: str | Path,
    conn: sqlite3.Connection,
    cursor: sqlite3.Cursor,
    execution_id: str,
    workflows: list[dict],
    agents_by_phase: dict[int, list],
    phase_idx: int,
    phase_context: dict,
    correction_text: str | None = None,
    all_phase_outputs_so_far: dict | None = None,
    trace_id: str | None = None,
    extra_context: dict | None = None,
) -> dict:
    """运行单个 HITL phase 并保存暂停状态。"""
    wf = workflows[phase_idx]
    phase_num = wf["phase"]
    phase_mode = wf.get("mode", "sequential")
    phase_agents = agents_by_phase.get(phase_num, [])

    lead_agent = _get_lead_agent(phase_agents)
    agent_names = _get_agent_names(phase_agents)

    # Create phase execution record (may already exist from initial creation)
    cursor.execute(
        "INSERT OR REPLACE INTO squad_phase_executions (execution_id, phase, phase_name, status, primary_agent, supporting_agents_json, started_at, outputs_json, success_criteria_met_json, metrics_json) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (execution_id, phase_num, wf.get("name", f"阶段 {phase_num}"), "running", lead_agent,
         json.dumps(agent_names), datetime.now().isoformat(), json.dumps({}), json.dumps([]),
         json.dumps({"mode": phase_mode, "hitl_phase": True})),
    )
    conn.commit()

    merged_context = dict(phase_context)
    if extra_context:
        merged_context.update(extra_context)
    result = _execute_single_phase(
        db_path, wf, phase_agents, phase_mode, merged_context,
        wf.get("squad_id", execution_id.split("-")[-1] if "-" in execution_id else ""),
        execution_id,
        trace_id=trace_id,
    )

    phase_status = result.get("status", "failed")
    phase_outputs = result.get("outputs", {})
    phase_duration_min = result.get("duration_minutes", 0)

    # 从 merged_context 读取 token 积累
    phase_token_input = merged_context.get("_phase_token_input", 0)
    phase_token_output = merged_context.get("_phase_token_output", 0)
    phase_token_used = merged_context.get("_phase_token_used", 0)
    phase_token_model = merged_context.get("_phase_token_model", "")

    phase_metrics = {"mode": phase_mode, "duration_minutes": phase_duration_min, "hitl_phase": True,
                     "token_input": phase_token_input, "token_output": phase_token_output,
                     "token_used": phase_token_used, "token_model": phase_token_model}
    cursor.execute(
        "UPDATE squad_phase_executions SET status=?, completed_at=?, duration_minutes=?, outputs_json=?, metrics_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=? AND phase=?",
        (phase_status, datetime.now().isoformat(), phase_duration_min,
         json.dumps(phase_outputs, ensure_ascii=False),
         json.dumps(phase_metrics, ensure_ascii=False),
         execution_id, phase_num),
    )

    completed_phases_now = 1 if phase_status == "completed" else 0
    failed_phases_now = 0 if phase_status == "completed" else 1

    # Build aggregated outputs
    all_outputs = dict(all_phase_outputs_so_far or {})
    all_outputs[f"phase_{phase_num}"] = phase_outputs

    # Update context for next phase
    new_context = dict(phase_context)
    new_context["previous_phase_output"] = phase_outputs
    new_context["all_phase_outputs"] = all_outputs
    # 跨阶段传递契约 ID，使下一阶段智能体能感知前一阶段产出
    contract_ids = merged_context.get("_contract_ids", [])
    if contract_ids:
        existing = new_context.setdefault("_contract_ids", [])
        for cid in contract_ids:
            if cid not in existing:
                existing.append(cid)
    if correction_text:
        new_context["last_correction"] = correction_text

    is_last_phase = phase_idx >= len(workflows) - 1

    if is_last_phase:
        # Final phase — complete execution
        final_status = "completed" if phase_status == "completed" else "completed_with_errors"
        cursor.execute(
            "UPDATE squad_executions SET status=?, completed_at=CURRENT_TIMESTAMP, progress_percent=100.0, current_phase=?, result_json=?, outputs_json=?, metrics_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=?",
            (final_status, phase_num,
             json.dumps({"type": "hitl_complete", "phase_index": phase_idx, "phase_num": phase_num}, ensure_ascii=False),
             json.dumps(all_outputs, ensure_ascii=False),
             json.dumps({"total_phases": len(workflows), "completed_phases": completed_phases_now, "failed_phases": failed_phases_now, "hitl": True}, ensure_ascii=False),
             execution_id),
        )
        return {
            "phase_num": phase_num,
            "phase_name": wf.get("name", f"阶段 {phase_num}"),
            "status": phase_status,
            "outputs": phase_outputs,
            "all_outputs": all_outputs,
            "duration_minutes": phase_duration_min,
            "token_input": phase_token_input,
            "token_output": phase_token_output,
            "token_used": phase_token_used,
            "token_model": phase_token_model,
            "completed_phases": completed_phases_now,
            "failed_phases": failed_phases_now,
            "next_status": final_status,
        }

    # Save paused state for next phase (含 trace_id 供 advance 复用)
    hitl_state = {
        "type": "hitl_paused",
        "phase_index": phase_idx,
        "phase_num": phase_num,
        "trace_id": trace_id,
        "completed_phases": completed_phases_now,
        "failed_phases": failed_phases_now,
        "phase_context": new_context,
        "all_phase_outputs": all_outputs,
    }

    progress = ((phase_idx + 1) / len(workflows)) * 100
    cursor.execute(
        "UPDATE squad_executions SET status='paused', current_phase=?, progress_percent=?, result_json=?, outputs_json=?, updated_at=CURRENT_TIMESTAMP WHERE execution_id=?",
        (phase_num, progress,
         json.dumps(hitl_state, ensure_ascii=False),
         json.dumps(all_outputs, ensure_ascii=False),
         execution_id),
    )

    return {
        "phase_num": phase_num,
        "phase_name": wf.get("name", f"阶段 {phase_num}"),
        "status": phase_status,
        "outputs": phase_outputs,
        "all_outputs": all_outputs,
        "duration_minutes": phase_duration_min,
        "token_input": phase_token_input,
        "token_output": phase_token_output,
        "token_used": phase_token_used,
        "token_model": phase_token_model,
        "completed_phases": completed_phases_now,
        "failed_phases": failed_phases_now,
        "next_status": "paused",
    }

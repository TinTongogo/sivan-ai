"""周报数据访问服务。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from interfaces.api.services.base import _connect


def get_weekly_reports(db_path: str | Path, limit: int = 10) -> list[dict[str, Any]]:
    """获取周报列表。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT report_id, report_type, period_start, period_end, generated_at, total_executions, "
            "successful_executions, total_tokens_used, total_cost_usd, is_published, summary_markdown "
            "FROM weekly_reports ORDER BY generated_at DESC LIMIT ?",
            (limit,),
        )
        reports = []
        for row in cursor.fetchall():
            r = dict(row)
            if r.get("summary_markdown"):
                r["summary_markdown"] = r["summary_markdown"][:150] + "..." if len(r["summary_markdown"]) > 150 else r["summary_markdown"]
            reports.append(r)
        conn.close()
        return reports
    except Exception:
        return []


def get_weekly_report_detail(db_path: str | Path, report_id: str) -> dict[str, Any]:
    """获取周报详情。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM weekly_reports WHERE report_id = ?", (report_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"error": "Report not found"}
        report = dict(row)
        json_fields = [
            "top_performing_agents_json", "most_used_agents_json", "top_routing_strategies_json",
            "cost_by_agent_json", "cost_by_model_json", "most_used_skills_json", "skill_usage_trend_json",
            "contract_types_distribution_json", "performance_trend_json", "improvement_areas_json",
            "recommendations_json", "detailed_analysis_json", "charts_config_json",
        ]
        for field in json_fields:
            if report.get(field):
                try:
                    report[field] = json.loads(report[field])
                except Exception:
                    report[field] = {}
        conn.close()
        return report
    except Exception as e:
        return {"error": str(e)}


def generate_weekly_report(db_path: str | Path, report_data: dict[str, Any]) -> dict[str, Any]:
    """生成周报。"""
    try:
        report_type = report_data.get("report_type", "weekly")
        period_start = report_data.get("period_start")
        period_end = report_data.get("period_end")
        if not period_start or not period_end:
            return {"success": False, "error": "period_start and period_end are required"}

        if report_type == "weekly":
            start_date = datetime.strptime(period_start, "%Y-%m-%d")
            report_id = f"weekly-{start_date.year}-W{start_date.isocalendar()[1]}"
        else:
            report_id = f"{report_type}-{period_start}-to-{period_end}"

        stats = collect_system_stats_for_report(db_path, period_start, period_end)

        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT report_id FROM weekly_reports WHERE report_id = ?", (report_id,))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE weekly_reports SET generated_at=CURRENT_TIMESTAMP, total_executions=?, successful_executions=?, "
                "failed_executions=?, avg_duration_hours=?, active_squads=?, routing_decisions_total=?, "
                "routing_success_rate=?, total_tokens_used=?, total_cost_usd=?, total_skills_used=?, "
                "contracts_created=?, contracts_approved=?, summary_markdown=?, generated_by=? WHERE report_id=?",
                (stats.get("total_executions", 0), stats.get("successful_executions", 0),
                 stats.get("failed_executions", 0), stats.get("avg_duration_hours", 0),
                 stats.get("active_squads", 0), stats.get("routing_decisions_total", 0),
                 stats.get("routing_success_rate", 0), stats.get("total_tokens_used", 0),
                 stats.get("total_cost_usd", 0), stats.get("total_skills_used", 0),
                 stats.get("contracts_created", 0), stats.get("contracts_approved", 0),
                 stats.get("summary_markdown", ""), "system", report_id),
            )
        else:
            cursor.execute(
                "INSERT INTO weekly_reports (report_id, report_type, period_start, period_end, total_executions, "
                "successful_executions, failed_executions, avg_duration_hours, active_squads, routing_decisions_total, "
                "routing_success_rate, total_tokens_used, total_cost_usd, total_skills_used, contracts_created, "
                "contracts_approved, summary_markdown, generated_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (report_id, report_type, period_start, period_end, stats.get("total_executions", 0),
                 stats.get("successful_executions", 0), stats.get("failed_executions", 0),
                 stats.get("avg_duration_hours", 0), stats.get("active_squads", 0),
                 stats.get("routing_decisions_total", 0), stats.get("routing_success_rate", 0),
                 stats.get("total_tokens_used", 0), stats.get("total_cost_usd", 0),
                 stats.get("total_skills_used", 0), stats.get("contracts_created", 0),
                 stats.get("contracts_approved", 0), stats.get("summary_markdown", ""), "system"),
            )
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Report {report_id} generated successfully", "report_id": report_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def collect_system_stats_for_report(db_path: str | Path, period_start: str, period_end: str) -> dict[str, Any]:
    """收集系统统计数据用于报告。"""
    stats = {
        "total_executions": 0, "successful_executions": 0, "failed_executions": 0,
        "avg_duration_hours": 0, "active_squads": 0, "most_used_squad": None, "most_successful_squad": None,
        "top_performing_agents_json": "[]", "most_used_agents_json": "[]",
        "routing_decisions_total": 0, "routing_success_rate": 0, "top_routing_strategies_json": "[]",
        "total_tokens_used": 0, "total_cost_usd": 0, "cost_by_agent_json": "[]", "cost_by_model_json": "[]",
        "total_skills_used": 0, "most_used_skills_json": "[]",
        "contracts_created": 0, "contracts_approved": 0, "contract_types_distribution_json": "[]",
        "performance_trend_json": "[]", "improvement_areas_json": "[]", "recommendations_json": "[]",
        "summary_markdown": f"## {period_start} 至 {period_end} 系统性能报告\n\n*暂无数据*",
    }

    try:
        conn = _connect(db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful, "
            "SUM(CASE WHEN status IN ('failed','cancelled') THEN 1 ELSE 0 END) as failed, "
            "AVG(actual_duration_hours) as avg_duration FROM squad_executions WHERE DATETIME(started_at, 'localtime') BETWEEN ? AND ?",
            (period_start, period_end),
        )
        row = cursor.fetchone()
        if row and row["total"]:
            stats["total_executions"] = row["total"]
            stats["successful_executions"] = row["successful"] or 0
            stats["failed_executions"] = row["failed"] or 0
            stats["avg_duration_hours"] = round(row["avg_duration"] or 0, 2)

        cursor.execute(
            "SELECT COUNT(DISTINCT squad_id) as cnt FROM squad_executions "
            "WHERE DATETIME(started_at, 'localtime') BETWEEN ? AND ? AND status IN ('running', 'completed')",
            (period_start, period_end),
        )
        row = cursor.fetchone()
        if row:
            stats["active_squads"] = row["cnt"]

        cursor.execute(
            "SELECT name, COUNT(*) as cnt FROM squad_executions "
            "WHERE DATETIME(started_at, 'localtime') BETWEEN ? AND ? GROUP BY squad_id ORDER BY cnt DESC LIMIT 1",
            (period_start, period_end),
        )
        row = cursor.fetchone()
        if row:
            stats["most_used_squad"] = row["name"]

        cursor.execute(
            "SELECT primary_agent, COUNT(*) as cnt, SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success_cnt "
            "FROM squad_phase_executions WHERE DATETIME(started_at, 'localtime') BETWEEN ? AND ? GROUP BY primary_agent ORDER BY cnt DESC",
            (period_start, period_end),
        )
        agent_rows = cursor.fetchall()
        if agent_rows:
            stats["most_used_agents_json"] = json.dumps([{"agent": r["primary_agent"], "count": r["cnt"]} for r in agent_rows], ensure_ascii=False)
            sorted_agents = sorted(agent_rows, key=lambda r: (r["success_cnt"] / r["cnt"]) if r["cnt"] > 0 else 0, reverse=True)
            stats["top_performing_agents_json"] = json.dumps(
                [{"agent": r["primary_agent"], "success_rate": round((r["success_cnt"] / r["cnt"] * 100) if r["cnt"] > 0 else 0, 1)} for r in sorted_agents],
                ensure_ascii=False,
            )

        cursor.execute(
            "SELECT SUM(total_tokens) as total_tokens, SUM(cost_usd) as total_cost FROM token_usage WHERE DATETIME(timestamp, 'localtime') BETWEEN ? AND ?",
            (period_start, period_end),
        )
        row = cursor.fetchone()
        if row and row["total_tokens"]:
            stats["total_tokens_used"] = row["total_tokens"]
            stats["total_cost_usd"] = round(row["total_cost"] or 0, 4)

        cursor.execute(
            "SELECT agent_name, SUM(total_tokens) as tokens, SUM(cost_usd) as cost FROM token_usage "
            "WHERE DATETIME(timestamp, 'localtime') BETWEEN ? AND ? GROUP BY agent_name ORDER BY tokens DESC",
            (period_start, period_end),
        )
        cost_agent_rows = cursor.fetchall()
        if cost_agent_rows:
            stats["cost_by_agent_json"] = json.dumps([{"agent": r["agent_name"], "tokens": r["tokens"], "cost": round(r["cost"] or 0, 4)} for r in cost_agent_rows], ensure_ascii=False)

        cursor.execute(
            "SELECT model, SUM(total_tokens) as tokens, SUM(cost_usd) as cost FROM token_usage "
            "WHERE DATETIME(timestamp, 'localtime') BETWEEN ? AND ? GROUP BY model ORDER BY tokens DESC",
            (period_start, period_end),
        )
        cost_model_rows = cursor.fetchall()
        if cost_model_rows:
            stats["cost_by_model_json"] = json.dumps([{"model": r["model"], "tokens": r["tokens"], "cost": round(r["cost"] or 0, 4)} for r in cost_model_rows], ensure_ascii=False)

        cursor.execute(
            "SELECT skill_id, COUNT(*) as cnt FROM skill_usage WHERE DATETIME(timestamp, 'localtime') BETWEEN ? AND ? GROUP BY skill_id ORDER BY cnt DESC",
            (period_start, period_end),
        )
        skill_rows = cursor.fetchall()
        if skill_rows:
            stats["total_skills_used"] = len(skill_rows)
            stats["most_used_skills_json"] = json.dumps([{"skill": r["skill_id"], "count": r["cnt"]} for r in skill_rows[:10]], ensure_ascii=False)
        conn.close()
    except Exception as e:
        print(f"[Report] sivan.db 查询失败: {e}")

    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) as total, CAST(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS REAL) / COUNT(*) as success_rate "
            "FROM routing_decisions WHERE DATE(DATETIME(created_at, 'localtime')) BETWEEN ? AND ?",
            (period_start, period_end),
        )
        row = cursor.fetchone()
        if row and row["total"]:
            stats["routing_decisions_total"] = row["total"]
            stats["routing_success_rate"] = round(row["success_rate"] or 0, 4)

        cursor.execute(
            "SELECT routing_strategy, COUNT(*) as cnt, SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_cnt "
            "FROM routing_decisions WHERE DATE(DATETIME(created_at, 'localtime')) BETWEEN ? AND ? GROUP BY routing_strategy ORDER BY cnt DESC",
            (period_start, period_end),
        )
        strategy_rows = cursor.fetchall()
        if strategy_rows:
            stats["top_routing_strategies_json"] = json.dumps(
                [{"strategy": r["routing_strategy"], "count": r["cnt"], "success_rate": round((r["success_cnt"] / r["cnt"] * 100) if r["cnt"] > 0 else 0, 1)} for r in strategy_rows],
                ensure_ascii=False,
            )

        cursor.execute(
            "SELECT COUNT(*) as total, SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved "
            "FROM contracts WHERE DATE(DATETIME(created_at, 'localtime')) BETWEEN ? AND ?",
            (period_start, period_end),
        )
        row = cursor.fetchone()
        if row and row["total"]:
            stats["contracts_created"] = row["total"]
            stats["contracts_approved"] = row["approved"] or 0

        cursor.execute(
            "SELECT contract_type, COUNT(*) as cnt FROM contracts WHERE DATE(DATETIME(created_at, 'localtime')) BETWEEN ? AND ? GROUP BY contract_type ORDER BY cnt DESC",
            (period_start, period_end),
        )
        type_rows = cursor.fetchall()
        if type_rows:
            stats["contract_types_distribution_json"] = json.dumps([{"type": r["contract_type"], "count": r["cnt"]} for r in type_rows], ensure_ascii=False)
        conn.close()
    except Exception as e:
        print(f"[Report] 路由/契约查询失败: {e}")

    lines = [
        f"## {period_start} 至 {period_end} 系统性能报告\n",
        "### 执行概览",
        f"- 总执行次数: {stats['total_executions']}",
        f"- 成功: {stats['successful_executions']} | 失败: {stats['failed_executions']}",
    ]
    if stats["total_executions"] > 0:
        sr = round(stats["successful_executions"] / stats["total_executions"] * 100, 1)
        lines.append(f"- 成功率: {sr}%")
    if stats["avg_duration_hours"]:
        lines.append(f"- 平均耗时: {stats['avg_duration_hours']} 小时")
    if stats["active_squads"]:
        lines.append(f"- 活跃Squad: {stats['active_squads']}")
    if stats["routing_decisions_total"]:
        lines.append("\n### 路由系统")
        lines.append(f"- 路由决策: {stats['routing_decisions_total']} 次")
        lines.append(f"- 路由成功率: {round(stats['routing_success_rate'] * 100, 1)}%")
    if stats["total_tokens_used"]:
        lines.append("\n### 资源消耗")
        lines.append(f"- Token使用: {stats['total_tokens_used']:,}")
        lines.append(f"- 总成本: ${stats['total_cost_usd']:.4f}")
    if stats["contracts_created"]:
        lines.append("\n### 契约")
        lines.append(f"- 创建契约: {stats['contracts_created']} | 已批准: {stats['contracts_approved']}")

    stats["summary_markdown"] = "\n".join(lines)
    return stats


def publish_weekly_report(db_path: str | Path, report_id: str) -> dict[str, Any]:
    """发布周报。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE weekly_reports SET is_published = TRUE, published_at = CURRENT_TIMESTAMP WHERE report_id = ?", (report_id,))
        if cursor.rowcount == 0:
            conn.close()
            return {"success": False, "error": f"Report {report_id} not found"}
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Report {report_id} published successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_weekly_report(db_path: str | Path, report_id: str) -> dict[str, Any]:
    """删除周报。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM weekly_reports WHERE report_id = ?", (report_id,))
        rc = cursor.rowcount
        conn.commit()
        conn.close()
        if rc == 0:
            return {"success": False, "error": f"报告 {report_id} 不存在"}
        return {"success": True, "message": f"报告 {report_id} 已删除"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def download_weekly_report_html(db_path: str | Path, report_id: str) -> dict[str, Any]:
    """生成可下载的HTML报告。"""
    try:
        report = get_weekly_report_detail(db_path, report_id)
        if "error" in report:
            return {"success": False, "error": report["error"]}

        summary_md = report.get("summary_markdown", "*暂无数据*")
        html_lines, in_list = [], False
        for line in summary_md.split("\n"):
            if line.startswith("### "):
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.startswith("## "):
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("- "):
                if not in_list: html_lines.append("<ul>"); in_list = True
                html_lines.append(f"<li>{line[2:]}</li>")
            elif line.strip() == "":
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append("<p></p>")
            else:
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append(f"<p>{line}</p>")
        if in_list:
            html_lines.append("</ul>")
        content_html = "\n".join(html_lines)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<title>{report.get("report_id", "报告")}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }}
  .header {{ background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
  .header h1 {{ margin: 0 0 8px; font-size: 24px; }}
  .header .meta {{ opacity: 0.9; font-size: 14px; }}
  h2 {{ color: #4361ee; border-bottom: 2px solid #e8edff; padding-bottom: 8px; margin-top: 28px; }}
  h3 {{ color: #3a0ca3; margin-top: 20px; }}
  li {{ margin: 6px 0; }}
  .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 12px; color: #999; text-align: center; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin: 20px 0; }}
  .stat-card {{ background: #f8f9fa; border-radius: 8px; padding: 16px; text-align: center; }}
  .stat-card .num {{ font-size: 28px; font-weight: 700; color: #4361ee; }}
  .stat-card .label {{ font-size: 13px; color: #666; margin-top: 4px; }}
  @media print {{ body {{ margin: 0; padding: 10px; }} .header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }} }}
</style></head>
<body>
  <div class="header">
    <h1>{report.get("report_id", "系统报告")}</h1>
    <div class="meta">
      {report.get("period_start", "")} 至 {report.get("period_end", "")}
       | 类型: {report.get("report_type", "weekly")}
       | 生成于: {report.get("generated_at", "")}
    </div>
  </div>
  <div class="stats">
    <div class="stat-card"><div class="num">{report.get("total_executions", 0)}</div><div class="label">执行次数</div></div>
    <div class="stat-card"><div class="num" style="color:#28a745;">{report.get("successful_executions", 0)}</div><div class="label">成功执行</div></div>
    <div class="stat-card"><div class="num" style="color:#dc3545;">{report.get("failed_executions", 0)}</div><div class="label">失败执行</div></div>
    <div class="stat-card"><div class="num">${report.get("total_cost_usd", 0):.2f}</div><div class="label">总成本</div></div>
  </div>
  <div class="content">
    {content_html}
  </div>
  <div class="footer">
    <p>由 Sivan 系统自动生成 | 报告ID: {report.get("report_id", "")}</p>
  </div>
</body></html>"""
        return {"success": True, "html": html, "filename": f"{report.get('report_id', 'report')}.html"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def subscribe_report(db_path: str | Path, subscription: dict[str, Any]) -> dict[str, Any]:
    """订阅报告。"""
    try:
        email = subscription.get("email")
        report_type = subscription.get("report_type")
        if not email or not report_type:
            return {"success": False, "error": "email and report_type are required"}
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM report_subscriptions WHERE email = ? AND report_type = ?", (email, report_type))
        if cursor.fetchone():
            cursor.execute("UPDATE report_subscriptions SET is_active = TRUE, unsubscribed_at = NULL WHERE email = ? AND report_type = ?", (email, report_type))
        else:
            cursor.execute(
                "INSERT INTO report_subscriptions (email, report_type, delivery_method, delivery_config_json) VALUES (?, ?, ?, ?)",
                (email, report_type, subscription.get("delivery_method", "email"), json.dumps(subscription.get("delivery_config", {}))),
            )
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Subscribed to {report_type} reports for {email}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def unsubscribe_report(db_path: str | Path, email: str, report_type: str) -> dict[str, Any]:
    """取消订阅报告。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE report_subscriptions SET is_active = FALSE, unsubscribed_at = CURRENT_TIMESTAMP WHERE email = ? AND report_type = ?", (email, report_type))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Unsubscribed {email} from {report_type} reports"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_subscriptions(db_path: str | Path, email: str | None = None, report_type: str | None = None) -> list[dict[str, Any]]:
    """获取订阅列表。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        query = "SELECT * FROM report_subscriptions WHERE 1=1"
        params: list[Any] = []
        if email:
            query += " AND email = ?"
            params.append(email)
        if report_type:
            query += " AND report_type = ?"
            params.append(report_type)
        query += " ORDER BY subscribed_at DESC"
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results
    except Exception:
        return []


def check_and_generate_weekly_report(db_path: str | Path) -> None:
    """启动时检查并自动生成周报（如果尚未生成本周周报）。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(generated_at) as last_gen FROM weekly_reports WHERE report_type = 'weekly'")
        row = cursor.fetchone()
        last_gen = row["last_gen"] if row and row["last_gen"] else None
        conn.close()

        now = datetime.now()
        if last_gen:
            last_dt = datetime.strptime(last_gen[:10], "%Y-%m-%d") if isinstance(last_gen, str) else datetime.strptime(str(last_gen)[:10], "%Y-%m-%d")
            if (now - last_dt).days <= 7:
                return

        monday = now - timedelta(days=now.weekday())
        sunday = monday + timedelta(days=6)
        period_start = monday.strftime("%Y-%m-%d")
        period_end = sunday.strftime("%Y-%m-%d")
        result = generate_weekly_report(db_path, {"report_type": "weekly", "period_start": period_start, "period_end": period_end})
        if result.get("success"):
            print(f"[Report] 周报已自动生成: {result.get('report_id')}")
        else:
            print(f"[Report] 周报自动生成失败: {result.get('error')}")
    except Exception as e:
        print(f"[Report] 周报自动生成调度失败: {e}")


def get_active_subscriptions(db_path: str | Path, report_type: str) -> list[dict[str, Any]]:
    """获取指定报告类型的活跃订阅。"""
    try:
        conn = _connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, email, delivery_method, delivery_config_json FROM report_subscriptions WHERE report_type = ? AND is_active = TRUE",
            (report_type,),
        )
        results = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return results
    except Exception:
        return []

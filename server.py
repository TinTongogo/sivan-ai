"""Sivan 统一入口

Usage:
  python server.py              启动 Web + MCP 综合服务（默认）
  python server.py --mcp-stdio  以 STDIO 模式启动 MCP 服务（用于 Claude Desktop）
"""
from __future__ import annotations

import sys

if __name__ == "__main__":
    if "--mcp-stdio" in sys.argv:
        from interfaces.mcp.server import main as mcp_main
        mcp_main(transport="stdio")
    else:
        from interfaces.api.admin import logger, main

        try:
            main()
        except KeyboardInterrupt:
            logger.info("管理控制台已停止")
        except Exception as e:
            logger.error("管理控制台启动失败: %s", e)
            import traceback

            traceback.print_exc()

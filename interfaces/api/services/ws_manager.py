"""WebSocket 连接管理器。

维护每个 conversation_id 的活跃连接列表，支持广播推送。
"""

from __future__ import annotations

from fastapi import WebSocket


class WSConnectionManager:
    """按 conversation_id 管理的 WebSocket 连接池。"""

    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, conversation_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(conversation_id, []).append(ws)

    def disconnect(self, conversation_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(conversation_id, [])
        if ws in conns:
            conns.remove(ws)

    async def broadcast(self, conversation_id: str, data: dict) -> None:
        """向某对话的所有客户端推送 JSON 消息。"""
        dead: list[WebSocket] = []
        for ws in self._connections.get(conversation_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(conversation_id, ws)

    @property
    def active_connections(self) -> dict[str, int]:
        return {cid: len(ws_list) for cid, ws_list in self._connections.items()}


_manager: WSConnectionManager | None = None


def get_ws_manager() -> WSConnectionManager:
    global _manager
    if _manager is None:
        _manager = WSConnectionManager()
    return _manager

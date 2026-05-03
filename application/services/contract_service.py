"""契约应用服务。

组合契约仓库与事件发布，提供契约管理用例。
"""

from __future__ import annotations

from typing import Any

from domain.contract.repository import IContractRepository


class ContractService:
    """契约应用服务。"""

    def __init__(self, contract_repo: IContractRepository) -> None:
        self._repo = contract_repo

    def create(self, contract_type: str, content: dict[str, Any], created_by: str) -> str:
        return self._repo.create(contract_type, content, created_by)

    def get(self, contract_id: str) -> dict[str, Any] | None:
        return self._repo.find_by_id(contract_id)

    def update(self, contract_id: str, updates: dict[str, Any]) -> bool:
        return self._repo.update(contract_id, updates)

    def find(
        self,
        contract_type: str | None = None,
        status: str | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        return self._repo.find(contract_type, status, tag, limit)

    def get_stats(self) -> dict[str, Any]:
        return self._repo.get_stats()

"""契约领域实体。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Contract:
    """契约实体。"""
    contract_id: str
    contract_type: str  # global, api, ui, data, model
    content: dict[str, Any]
    created_by: str
    created_at: str
    updated_at: str
    version: str = "1.0.0"
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    status: str = "draft"  # draft, reviewed, approved, deprecated
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "contract_type": self.contract_type,
            "content": self.content,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "tags": list(self.tags),
            "dependencies": list(self.dependencies),
            "status": self.status,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

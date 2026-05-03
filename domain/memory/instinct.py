"""本能模板领域实体。

InstinctPattern 表示一个经过验证成功的高频任务 → 编排拓扑映射。
当同一类型任务连续成功 ≥10 次且成功率 >80%，自动激活为"本能"，
后续同类任务跳过动态生成，直接使用冻结拓扑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class InstinctPattern:
    """本能模板实体。

    记录任务特征与成功编排拓扑的映射关系，
    当 confidence 足够高时自动激活，绕过动态拓扑生成。
    """

    pattern_id: str
    task_type: str
    task_signature: str          # 归一化任务特征
    topology_json: str           # 冻结的编排拓扑 JSON
    success_count: int = 0
    total_count: int = 0
    confidence: float = 0.0
    is_active: bool = False      # ≥10 次成功且 confidence>0.8 时激活
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """计算成功率。"""
        if self.total_count == 0:
            return 0.0
        return self.success_count / self.total_count

    def record_outcome(self, success: bool) -> None:
        """记录一次执行结果，更新置信度。"""
        self.total_count += 1
        if success:
            self.success_count += 1
        self.confidence = self.success_rate
        self.updated_at = datetime.now()

        # 自动激活条件：≥10 次且成功率 >80%
        if self.total_count >= 10 and self.success_rate > 0.8:
            self.is_active = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "task_type": self.task_type,
            "task_signature": self.task_signature,
            "topology_json": self.topology_json,
            "success_count": self.success_count,
            "total_count": self.total_count,
            "confidence": round(self.confidence, 4),
            "success_rate": round(self.success_rate, 4),
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at),
            "updated_at": self.updated_at.isoformat() if hasattr(self.updated_at, "isoformat") else str(self.updated_at),
        }

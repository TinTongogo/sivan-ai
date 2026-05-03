"""ML 分类器端口（六边形架构 Port）。

领域层定义抽象接口，基础设施层（scikit-learn）实现。
"""

from abc import ABC, abstractmethod


class MLClassifierPort(ABC):
    """ML 分类器端口：文本 → 智能体得分映射。"""

    @abstractmethod
    def predict(self, text: str, candidates: list[str]) -> dict[str, float]:
        """预测文本属于各候选智能体的得分。"""
        ...

    @abstractmethod
    def train(self, texts: list[str], labels: list[str]) -> None:
        """训练分类器。"""
        ...

    @property
    @abstractmethod
    def is_trained(self) -> bool:
        """是否已完成训练。"""
        ...

"""领域层通用接口定义。

跨领域共享的抽象接口：事件发布、日志、缓存等。
具体实现由基础设施层提供（依赖倒置原则）。
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from domain.common.value_object import MemoryLevel


class IContextInjector(ABC):
    """记忆上下文注入器接口，用于将相关记忆注入到 system_prompt。"""

    @abstractmethod
    def build_context(
        self,
        query: str,
        scope_ids: dict[MemoryLevel, str] | None = None,
        top_k: int = 5,
    ) -> str:
        """构建记忆上下文文本。"""
        ...

    @abstractmethod
    def inject_to_prompt(self, system_prompt: str, memory_context: str) -> str:
        """将记忆上下文注入到 system_prompt。"""
        ...


class IEventPublisher(ABC):
    """事件发布器接口 (Observer 模式)。"""

    @abstractmethod
    def publish(self, event_name: str, data: dict[str, Any]) -> None:
        """发布领域事件。"""
        ...

    @abstractmethod
    def subscribe(self, event_name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """订阅领域事件。"""
        ...

    @abstractmethod
    def unsubscribe(self, event_name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        """取消订阅。"""
        ...


class ILogger(ABC):
    """日志记录器接口。"""

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None: ...
    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None: ...
    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None: ...
    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None: ...


class IMemoryStore(ABC):
    """记忆存储接口 (Cache-aside 模式)。"""

    @abstractmethod
    def get(self, key: str) -> Any | None: ...
    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def clear(self) -> None: ...

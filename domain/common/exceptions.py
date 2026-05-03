"""领域层异常定义。"""


class DomainException(Exception):
    """领域异常基类。"""
    def __init__(self, message: str, code: str | None = None) -> None:
        self.code = code
        super().__init__(message)


class EntityNotFoundError(DomainException):
    """实体未找到。"""
    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} not found: {entity_id}",
            code="ENTITY_NOT_FOUND",
        )
        self.entity_type = entity_type
        self.entity_id = entity_id


class MemoryNotFoundError(EntityNotFoundError):
    """记忆条目未找到。"""
    def __init__(self, memory_id: str) -> None:
        super().__init__("MemoryEntry", memory_id)


class InvalidMemoryLevelError(DomainException):
    """无效的记忆层级。"""
    def __init__(self, level: str) -> None:
        super().__init__(
            message=f"Invalid memory level: {level}. Valid: session, user, team, project",
            code="INVALID_MEMORY_LEVEL",
        )
        self.level = level


class MemoryStorageError(DomainException):
    """记忆存储异常。"""
    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message=message, code="MEMORY_STORAGE_ERROR")
        self.cause = cause


class ValidationError(DomainException):
    """参数验证异常。"""
    def __init__(self, field: str, reason: str) -> None:
        super().__init__(
            message=f"Validation failed for {field}: {reason}",
            code="VALIDATION_ERROR",
        )
        self.field = field

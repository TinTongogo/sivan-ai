"""配置模块单元测试。"""

from __future__ import annotations

import os


class TestSettings:
    def test_default_db_path(self) -> None:
        """验证 DB_PATH 默认值使用 data/ 目录。"""
        from config.settings import settings
        assert "data" in settings.DB_PATH
        assert settings.DB_PATH.endswith("sivan.db")

    def test_auth_salt_from_env(self) -> None:
        """验证 AUTH_SALT 可从环境变量覆盖（P0 回归测试）。"""
        from config.settings import settings
        old_salt = settings.AUTH_SALT

        os.environ["SIVAN_AUTH_SALT"] = "custom-test-salt"
        # 重新导入获取新值（因为 settings 是模块级单例）
        import importlib
        import config.settings
        importlib.reload(config.settings)
        assert config.settings.settings.AUTH_SALT == "custom-test-salt"

        # 恢复
        del os.environ["SIVAN_AUTH_SALT"]
        importlib.reload(config.settings)
        assert config.settings.settings.AUTH_SALT == old_salt

    def test_default_auth_salt_fallback(self) -> None:
        """验证无环境变量时 AUTH_SALT 使用默认值。"""
        if "SIVAN_AUTH_SALT" in os.environ:
            del os.environ["SIVAN_AUTH_SALT"]
        from config.settings import settings
        assert settings.AUTH_SALT == "@sivan"

    def test_admin_host_default(self) -> None:
        from config.settings import settings
        assert settings.ADMIN_HOST == "127.0.0.1"

    def test_admin_port_default(self) -> None:
        from config.settings import settings
        assert settings.ADMIN_PORT == 8001

    def test_memory_config_defaults(self) -> None:
        from config.settings import settings
        assert settings.MEMORY_SESSION_TTL == 3600
        assert settings.MEMORY_MAX_CONTEXT_MEMORIES == 10

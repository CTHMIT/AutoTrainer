"""
# src/config.py
配置模組：處理所有系統配置
"""

import os
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class Priority(str, Enum):
    """任務優先級枚舉"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RedisConfig(BaseModel):
    """Redis 連接配置"""

    host: str = Field(default_factory=lambda: os.getenv("REDIS_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = Field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))
    password: Optional[str] = Field(default_factory=lambda: os.getenv("REDIS_PASSWORD"))

    def get_url(self) -> str:
        """返回 Redis 連接 URL"""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class WorkerConfig(BaseModel):
    """Worker 配置"""

    name: str = Field(default_factory=lambda: os.getenv("WORKER_NAME", "worker"))
    queues: List[str] = Field(default_factory=lambda: ["high", "medium", "low"])
    retry_limit: int = Field(default_factory=lambda: int(os.getenv("RETRY_LIMIT", "3")))
    timeout: int = Field(default=3600)


class APIConfig(BaseModel):
    """API 服務配置"""

    host: str = Field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = Field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    debug: bool = Field(default_factory=lambda: os.getenv("API_DEBUG", "0") == "1")
    webhook_url: Optional[str] = Field(default_factory=lambda: os.getenv("WEBHOOK_URL"))


class LogConfig(BaseModel):
    """日誌配置"""

    level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format: str = Field(default="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    file: Optional[str] = Field(default_factory=lambda: os.getenv("LOG_FILE"))


class Config(BaseModel):
    """應用總配置"""

    redis: RedisConfig = Field(default_factory=RedisConfig)
    worker: WorkerConfig = Field(default_factory=WorkerConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    log: LogConfig = Field(default_factory=LogConfig)


class ConfigManagerABC(ABC):
    """配置管理器抽象基類"""

    @abstractmethod
    def get_config(self) -> Config:
        """獲取配置"""
        pass

    @abstractmethod
    def reset(self) -> None:
        """重置配置"""
        pass


class EnvConfigManager(ConfigManagerABC):
    """基於環境變數的配置管理器（單例模式）"""

    _instance: Optional[Config] = None

    def get_config(self) -> Config:
        if self._instance is None:
            self._instance = Config()
            self._setup_logging()
        return self._instance

    def _setup_logging(self) -> None:
        """配置日誌系統"""
        assert self._instance is not None, "Config instance is not initialized"
        config = self._instance

        log_level = getattr(logging, config.log.level.upper(), logging.INFO)

        # 明確標註 handlers 的類型
        handlers: List[logging.Handler] = [logging.StreamHandler()]

        if config.log.file:
            os.makedirs(os.path.dirname(config.log.file), exist_ok=True)
            handlers.append(logging.FileHandler(config.log.file))  # ✅ 沒有錯誤

        logging.basicConfig(
            level=log_level, format=config.log.format, handlers=handlers
        )

    def reset(self) -> None:
        """重置配置（主要用於測試）"""
        self._instance = None


# 便捷函數
_config_manager = EnvConfigManager()


def get_config() -> Config:
    """獲取系統配置"""
    return _config_manager.get_config()


def reset_config() -> None:
    """重置系統配置"""
    _config_manager.reset()

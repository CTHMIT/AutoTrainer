"""
測試配置: 定義測試用的 fixtures
"""

import pytest
import fakeredis
from unittest.mock import MagicMock, patch
import typing
from src.config import get_config, _config_manager, Config


@pytest.fixture(autouse=True)
def reset_singletons() -> typing.Generator[None, None, None]:
    """自動重置所有單例模式"""
    # 重置配置單例
    _config_manager.reset()

    # 重置隊列管理器單例
    from src.core.queue import QueueManager

    QueueManager._instance = None

    yield


@pytest.fixture
def mock_redis() -> typing.Generator[fakeredis.FakeRedis, None, None]:
    """模擬 Redis 連接"""
    with patch("redis.Redis") as mock:
        mock_instance = MagicMock(spec=fakeredis.FakeRedis)
        mock.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def fake_redis() -> typing.Generator[fakeredis.FakeRedis, None, None]:
    """提供功能性的假 Redis 實例"""
    redis_instance = fakeredis.FakeRedis(decode_responses=True)
    with patch("redis.Redis", return_value=redis_instance):
        yield redis_instance


@pytest.fixture
def mock_job() -> typing.Generator[None, None, None]:
    """模擬 RQ Job"""
    mock = MagicMock()
    mock.id = "test-job-id"
    mock.get_status.return_value = "queued"
    mock.created_at = "2023-01-01T00:00:00"
    mock.meta = {}
    mock.origin = "medium"
    return mock


@pytest.fixture
def test_config() -> Config:
    """提供測試用配置"""
    # 重置配置單例
    _config_manager.reset()

    # 修改配置參數
    config = get_config()
    config.redis.host = "localhost"
    config.redis.port = 6379
    config.worker.retry_limit = 2

    return config

"""
基本測試: 確認主要組件正常工作
"""

from src.config import get_config, Priority


def test_config_singleton() -> None:
    """測試配置單例模式"""
    config1 = get_config()
    config2 = get_config()

    # 檢查是同一個對象
    assert config1 is config2

    # 檢查基本配置
    assert hasattr(config1, "redis")
    assert hasattr(config1, "worker")
    assert hasattr(config1, "api")
    assert hasattr(config1, "log")


def test_priority_enum() -> None:
    """測試優先級枚舉"""
    assert Priority.HIGH == "high"
    assert Priority.MEDIUM == "medium"
    assert Priority.LOW == "low"

    # 測試序列化
    assert Priority.HIGH.value == "high"


def test_package_imports() -> None:
    """測試基本導入"""
    # 測試主模組導入
    import src

    assert hasattr(src, "__version__")

    # 測試子模組導入
    from src import config

    assert callable(config.get_config)

    from src.core import queue

    assert callable(queue.get_queue_manager)

    from src.api import models

    assert hasattr(models, "JobStatus")

    from src.worker import worker

    assert callable(worker.run_worker)

    from src.scheduler import scheduler

    assert callable(scheduler.run_scheduler)

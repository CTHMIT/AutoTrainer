"""
Worker模組：負責執行排隊的任務
"""

import os
import signal
import logging
from typing import List, Any, Sequence, cast, Union
from redis import Redis
from rq import Worker, Queue
from rq.job import Job
from rq.registry import StartedJobRegistry

from src.config import get_config

logger = logging.getLogger(__name__)


class TrainingWorker(Worker):
    """自訂 RQ worker，處理任務取消與增強日誌功能"""

    def __init__(
        self, queues: List[Union[str, Queue]], *args: Any, **kwargs: Any
    ) -> None:
        """初始化 worker"""
        super().__init__(queues, *args, **kwargs)
        self.config = get_config()
        self.log_job_execution = True
        logger.info(f"Worker {self.name} 已初始化，監控隊列: {self.queue_names()}")

    def handle_job_success(
        self, job: Job, queue: Queue, started_job_registry: StartedJobRegistry
    ) -> Any:
        """
        處理任務成功完成

        Args:
            job: 完成的任務
            queue: 任務所在的隊列
            started_job_registry: 已啟動任務的註冊表

        Returns:
            Any: 父類方法的返回值
        """
        logger.info(f"任務 {job.id} 成功完成")
        return super().handle_job_success(job, queue, started_job_registry)

    def perform_job(self, job: Job, queue: Queue) -> Any:
        """
        執行任務，提供額外監控和取消支持

        Args:
            job: 要執行的任務
            queue: 任務來源隊列

        Returns:
            Any: 任務結果
        """
        if self.log_job_execution:
            logger.info(f"開始執行任務 {job.id}，來自隊列 {queue.name}")

        # 檢查取消請求
        if job.meta.get("cancel_requested", False):
            logger.info(f"任務 {job.id} 在執行前已被取消")
            return None

        # 執行任務並返回結果
        return super().perform_job(job, queue)


def get_queue_list(redis_conn: Redis) -> Sequence[Queue]:
    """
    獲取Worker應該處理的隊列列表

    Args:
        redis_conn: Redis連接

    Returns:
        Sequence[Queue]: 隊列對象列表
    """
    config = get_config()
    return [Queue(name=q, connection=redis_conn) for q in config.worker.queues]


def setup_signal_handlers(worker: Worker) -> None:
    """
    設置信號處理程序以優雅地關閉

    Args:
        worker: Worker 實例
    """

    def request_stop(signum: int, frame: Any) -> None:
        """信號處理程序，請求worker停止"""
        logger.info(f"收到信號 {signum}，正在關閉worker...")
        worker.request_stop(signum, frame)

    # 註冊信號處理程序
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)


def run_worker() -> None:
    """運行worker進程"""
    config = get_config()
    logger.info(f"啟動worker: {config.worker.name}")

    # 連接Redis
    redis_conn = Redis(
        host=config.redis.host,
        port=config.redis.port,
        db=config.redis.db,
        password=config.redis.password,
        decode_responses=True,
    )

    # 獲取隊列列表
    queues = get_queue_list(redis_conn)

    # 建立worker名稱
    hostname = os.uname().nodename
    pid = os.getpid()
    worker_name = f"{config.worker.name}.{hostname}.{pid}"

    # 顯示啟動消息
    queue_names = [q.name for q in queues]
    logger.info(f"Worker {worker_name} 啟動，監控隊列: {', '.join(queue_names)}")

    # 創建並啟動worker
    worker = TrainingWorker(
        queues=cast(List[Union[str, Queue]], queues),
        name=worker_name,
        connection=redis_conn,
        default_worker_ttl=600,
        default_result_ttl=5000,
        job_monitoring_interval=30,
    )

    # 設置信號處理程序
    setup_signal_handlers(worker)

    # 運行worker
    worker.work()


if __name__ == "__main__":
    # 獲取配置
    config = get_config()

    # 執行worker
    run_worker()

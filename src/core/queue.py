"""
# src/core/queue.py
隊列管理模組：處理基於Redis的任務隊列操作
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from redis import Redis
import rq
from rq import Queue
from rq.job import Job
from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
import rq.serializers

from src.config import get_config, Priority

logger = logging.getLogger(__name__)


class QueueManager:
    """隊列管理器，處理任務入列和監控（單例模式）"""

    _instance: Optional["QueueManager"] = None

    def __new__(cls) -> "QueueManager":
        """確保單例模式"""
        if cls._instance is None:
            cls._instance = super(QueueManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化隊列管理器"""
        if getattr(self, "_initialized", False):
            return

        config = get_config()

        # 建立Redis連接
        self.redis = Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            password=config.redis.password,
            decode_responses=True,
        )

        # 初始化隊列
        self.queues: Dict[str, Queue] = {}
        for queue_name in config.worker.queues:
            self.queues[queue_name] = Queue(
                name=queue_name,
                connection=self.redis,
                default_timeout=config.worker.timeout,
                serializer=rq.serializers.JSONSerializer(),
            )

        self._initialized = True
        logger.info(f"隊列管理器初始化完成，隊列：{list(self.queues.keys())}")

    def enqueue(
        self, func: Any, *args: Any, priority: Priority = Priority.MEDIUM, **kwargs: Any
    ) -> Job:
        """
        任務入列

        Args:
            func: 要執行的函數
            *args: 函數的位置參數
            priority: 任務優先級
            **kwargs: 函數的關鍵字參數

        Returns:
            Job: 入列的任務
        """
        queue = self.queues[priority.value]
        job = queue.enqueue(func, *args, **kwargs)
        logger.info(f"任務 {job.id} 已入列至 {priority.value} 優先級隊列")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        獲取任務資訊

        Args:
            job_id: 任務ID

        Returns:
            Optional[Job]: 如果找到則返回任務對象，否則返回None
        """
        try:
            return Job.fetch(job_id, connection=self.redis)
        except Exception as e:
            logger.error(f"獲取任務 {job_id} 失敗: {e}")
            return None

    def cancel_job(self, job_id: str, force: bool = False) -> Tuple[bool, str]:
        """
        取消任務

        Args:
            job_id: 任務ID
            force: 是否強制取消正在執行的任務

        Returns:
            Tuple[bool, str]: (成功標識, 描述訊息)
        """
        job = self.get_job(job_id)
        if not job:
            return False, "任務不存在"

        status = job.get_status()

        # 檢查任務狀態
        if status in ("finished", "failed"):
            return False, f"任務已{status}，無法取消"

        if status == "queued":
            # 直接取消排隊中的任務
            try:
                job.delete()
                return True, "任務已取消"
            except Exception as e:
                logger.error(f"取消任務 {job_id} 失敗: {e}")
                return False, f"取消任務失敗: {str(e)}"

        # 處理執行中的任務
        if force:
            # 標記任務為要求取消
            job.meta["cancel_requested"] = True
            job.save_meta()
            return True, "已請求取消任務，任務將在下一個檢查點停止"

        return False, "任務正在執行中，需要使用force=True強制取消"

    def list_jobs(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        列出所有任務

        Args:
            status_filter: 可選的狀態過濾器

        Returns:
            List[Dict[str, Any]]: 任務資訊列表
        """
        result = []

        # 從各狀態註冊表獲取任務
        for queue_name, queue in self.queues.items():
            # 排隊中的任務
            if not status_filter or status_filter == "queued":
                for job_id in queue.job_ids:
                    try:
                        job = Job.fetch(job_id, connection=self.redis)
                        if job.get_status() == "queued":
                            result.append(
                                {
                                    "id": job.id,
                                    "status": "queued",
                                    "queue": queue_name,
                                    "created_at": job.created_at,
                                    "func_name": job.func_name,
                                }
                            )
                    except Exception:
                        pass

            # 執行中的任務
            if not status_filter or status_filter == "started":
                registry = StartedJobRegistry(queue=queue)
                for job_id in registry.get_job_ids():
                    try:
                        job = Job.fetch(job_id, connection=self.redis)
                        result.append(
                            {
                                "id": job.id,
                                "status": "started",
                                "queue": queue_name,
                                "created_at": job.created_at,
                                "started_at": job.started_at,
                                "func_name": job.func_name,
                            }
                        )
                    except Exception:
                        pass

            # 已完成的任務
            if not status_filter or status_filter == "finished":
                registry = FinishedJobRegistry(queue=queue)
                for job_id in registry.get_job_ids():
                    try:
                        job = Job.fetch(job_id, connection=self.redis)
                        result.append(
                            {
                                "id": job.id,
                                "status": "finished",
                                "queue": queue_name,
                                "created_at": job.created_at,
                                "ended_at": job.ended_at,
                                "result": job.result,
                                "func_name": job.func_name,
                            }
                        )
                    except Exception:
                        pass

            # 失敗的任務
            if not status_filter or status_filter == "failed":
                registry = FailedJobRegistry(queue=queue)
                for job_id in registry.get_job_ids():
                    try:
                        job = Job.fetch(job_id, connection=self.redis)
                        result.append(
                            {
                                "id": job.id,
                                "status": "failed",
                                "queue": queue_name,
                                "created_at": job.created_at,
                                "ended_at": job.ended_at,
                                "error": job.exc_info,
                                "func_name": job.func_name,
                            }
                        )
                    except Exception:
                        pass

        return result


# 便捷函數
def get_queue_manager() -> QueueManager:
    """獲取隊列管理器"""
    return QueueManager()

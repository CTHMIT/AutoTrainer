"""
調度器模組：監控系統資源並協調任務執行
"""

import asyncio
import logging
import psutil  # type: ignore
import subprocess
import traceback
from typing import Dict, List, Any, Tuple, Optional, Union


from src.config import get_config
from src.core.queue import get_queue_manager

logger = logging.getLogger(__name__)


class ResourceMonitor:
    """監控系統資源使用情況"""

    def __init__(self) -> None:
        """初始化資源監控器"""
        self.config = get_config()
        self.max_cpu_usage = 80.0  # 最大CPU使用率閾值
        self.gpu_util_threshold = 20.0  # GPU閒置閾值

    async def check_cpu_available(self) -> bool:
        """
        檢查CPU資源是否可用

        Returns:
            bool: CPU使用率是否低於閾值
        """
        cpu_usage = psutil.cpu_percent(interval=0.5)
        available: bool = cpu_usage < self.max_cpu_usage
        if not available:
            logger.debug(f"CPU使用率 ({cpu_usage}%) 超過閾值 ({self.max_cpu_usage}%)")
        return available

    async def check_gpu_available(self) -> Tuple[bool, List[int]]:
        """
        檢查GPU資源是否可用

        Returns:
            Tuple[bool, List[int]]: (是否有可用GPU, 可用GPU索引列表)
        """
        try:
            # 使用nvidia-smi獲取GPU利用率
            gpu_info = subprocess.getoutput(
                "nvidia-smi --query-gpu=index,utilization.gpu --format=csv,noheader,nounits"
            )

            available_gpus = []
            for line in gpu_info.strip().splitlines():
                try:
                    idx, util = [x.strip() for x in line.split(",")]
                    if float(util) < self.gpu_util_threshold:
                        available_gpus.append(int(idx))
                except Exception as e:
                    logger.warning(f"解析GPU資料錯誤: {str(e)}")

            available = len(available_gpus) > 0
            if not available:
                logger.debug("沒有閒置的GPU")

            return available, available_gpus
        except Exception as e:
            # 如果nvidia-smi失敗，假設沒有GPU或不可用
            logger.debug(f"檢查GPU可用性失敗: {str(e)}")
            return False, []

    async def get_system_stats(self) -> Dict[str, Any]:
        """
        獲取詳細的系統統計信息

        Returns:
            Dict[str, Any]: 系統統計信息
        """
        mem = psutil.virtual_memory()

        stats: Dict[str, Any] = {
            "cpu": {
                "percent": psutil.cpu_percent(interval=0.1),
                "count": psutil.cpu_count(logical=True),
            },
            "memory": {
                "total": mem.total,
                "available": mem.available,
                "percent": mem.percent,
            },
            "gpu": [],
        }

        # 嘗試獲取GPU統計
        gpu_stats: List[Dict[str, Union[float, int]]] = []

        try:
            gpu_info = subprocess.getoutput(
                "nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total "
                "--format=csv,noheader,nounits"
            )

            for line in gpu_info.strip().splitlines():
                try:
                    idx, util, mem_used, mem_total = [
                        x.strip() for x in line.split(",")
                    ]
                    gpu_stats.append(
                        {
                            "index": int(idx),
                            "utilization": float(util),
                            "memory_used": float(mem_used),
                            "memory_total": float(mem_total),
                        }
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # Assign the populated list to stats
        stats["gpu"] = gpu_stats

        return stats


class Scheduler:
    """
    資源感知調度器，管理訓練任務
    實現單例模式
    """

    _instance: Optional["Scheduler"] = None

    def __new__(cls) -> "Scheduler":
        """確保單例模式"""
        if cls._instance is None:
            cls._instance = super(Scheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """初始化調度器"""
        if getattr(self, "_initialized", False):
            return

        self.resource_monitor = ResourceMonitor()
        self.queue_manager = get_queue_manager()
        self._running = False
        self._initialized = True

    async def run(self) -> None:
        """執行調度循環"""
        self._running = True
        logger.info("調度器已啟動")

        while self._running:
            try:
                # 檢查資源是否可用
                cpu_available = await self.resource_monitor.check_cpu_available()
                gpu_available, available_gpus = (
                    await self.resource_monitor.check_gpu_available()
                )

                if cpu_available and (gpu_available or not available_gpus):
                    # 資源可用，嘗試調度任務
                    await self._schedule_job(available_gpus)
                else:
                    logger.debug("資源不足，暫不調度新任務")

                # 等待一段時間再檢查
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"調度循環錯誤: {str(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(10)  # 出錯後等待更長時間

    async def _schedule_job(self, available_gpus: List[int]) -> None:
        """
        嘗試從優先級隊列中調度任務

        Args:
            available_gpus: 可用的GPU索引列表
        """
        # 獲取所有排隊中的任務
        jobs = self.queue_manager.list_jobs(status_filter="queued")

        # 按優先級分組
        priority_jobs: Dict[str, List[Dict[str, Any]]] = {
            "high": [],
            "medium": [],
            "low": [],
        }

        for job in jobs:
            queue = job.get("queue", "medium")
            if queue in priority_jobs:
                priority_jobs[queue].append(job)

        # 按優先級嘗試調度任務
        for priority in ["high", "medium", "low"]:
            if priority_jobs[priority]:
                # 按創建時間排序，優先處理最早創建的任務
                oldest_job = min(
                    priority_jobs[priority], key=lambda j: j.get("created_at", "")
                )
                job_id = oldest_job["id"]

                logger.info(f"調度任務 {job_id} (優先級: {priority})")

                # 在實際系統中，這裡可能進行更複雜的調度，例如：
                # 1. 為任務分配特定的GPU
                # 2. 設置環境變量
                # 3. 手動啟動特定的Worker進程

                # 但在RQ中，Worker會自動從隊列中獲取任務，所以我們不需要做特殊處理
                # 可以通過日誌記錄調度決策
                if available_gpus:
                    gpu_str = ", ".join(map(str, available_gpus))
                    logger.info(f"為任務 {job_id} 分配GPU: {gpu_str}")
                else:
                    logger.info(f"任務 {job_id} 將使用CPU執行")

                # 只調度一個任務然後退出
                break

    def stop(self) -> None:
        """停止調度器"""
        self._running = False
        logger.info("調度器正在停止")


async def run_scheduler() -> None:
    """運行調度器的協程"""
    scheduler = Scheduler()
    await scheduler.run()


if __name__ == "__main__":
    # 獲取配置
    config = get_config()

    # 運行調度器
    asyncio.run(run_scheduler())

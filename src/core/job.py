"""
# src/core/job.py
任務處理模組：定義任務邏輯和處理函數
"""

import time
import logging
import requests  # type: ignore[import-untyped]
import traceback  # type ignore
from typing import Dict, Any, Optional

from rq import get_current_job
from src.config import get_config

logger = logging.getLogger(__name__)


class JobResult:
    """任務結果類"""

    def __init__(
        self,
        model_name: str,
        epochs: int,
        elapsed_time: float,
        completed_epochs: int,
        metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        self.model_name = model_name
        self.epochs = epochs
        self.elapsed_time = elapsed_time
        self.completed_epochs = completed_epochs
        self.metrics = metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典用於序列化"""
        return {
            "model": self.model_name,
            "epochs": self.epochs,
            "completed_epochs": self.completed_epochs,
            "time": self.elapsed_time,
            "metrics": self.metrics,
        }


def send_webhook(event: str, payload: Dict[str, Any]) -> bool:
    """
    發送webhook通知

    Args:
        event: 事件類型
        payload: 事件數據

    Returns:
        bool: 是否成功發送
    """
    config = get_config()
    webhook_url = config.api.webhook_url

    if not webhook_url:
        return False

    try:
        data = {"event": event, **payload}
        response = requests.post(webhook_url, json=data, timeout=5)
        mode: bool = response.status_code >= 200 and response.status_code < 300
        return mode
    except Exception as e:
        logger.error(f"發送webhook失敗: {e}")
        return False


def train_model(model_name: str, epochs: int) -> Dict[str, Any]:
    """
    訓練模型任務(示例)

    Args:
        model_name: 模型名稱
        epochs: 訓練輪數

    Returns:
        Dict[str, Any]: 訓練結果
    """
    # 獲取當前任務對象
    job = get_current_job()
    job_id = job.id if job else "unknown"

    logger.info(f"開始任務 {job_id}: 訓練模型 {model_name}，{epochs} 輪")
    start_time = time.time()
    completed_epochs = 0

    try:
        # 模擬訓練過程
        for ep in range(1, epochs + 1):
            # 檢查取消請求
            if job:
                job.refresh()
                if job.meta.get("cancel_requested", False):
                    logger.warning(f"任務 {job_id} 已在第 {ep}/{epochs} 輪被取消")
                    result = JobResult(
                        model_name=model_name,
                        epochs=epochs,
                        elapsed_time=time.time() - start_time,
                        completed_epochs=ep - 1,
                    )
                    send_webhook(
                        "job_cancelled", {"job_id": job_id, "result": result.to_dict()}
                    )
                    raise InterruptedError("任務被用戶取消")

            # 記錄進度
            logger.info(f"[{job_id}] 訓練 {model_name}: 第 {ep}/{epochs} 輪")

            # 模擬訓練時間（實際專案中應替換為真實訓練代碼）
            time.sleep(1)
            completed_epochs = ep

            # 更新進度（可以被前端查詢）
            if job:
                job.meta["progress"] = ep / epochs * 100
                job.meta["current_epoch"] = ep
                job.save_meta()

        # 訓練完成
        elapsed_time = time.time() - start_time
        logger.info(
            f"任務 {job_id} 完成: 訓練 {model_name} {epochs} 輪，耗時 {elapsed_time:.2f} 秒"
        )

        # 建立結果對象
        result = JobResult(
            model_name=model_name,
            epochs=epochs,
            elapsed_time=elapsed_time,
            completed_epochs=completed_epochs,
            metrics={"accuracy": 0.95, "loss": 0.05},  # 模擬結果
        )

        # 發送Webhook通知
        send_webhook("job_completed", {"job_id": job_id, "result": result.to_dict()})

        return result.to_dict()

    except InterruptedError:
        # 重新拋出中斷異常
        raise
    except Exception as e:
        # 記錄錯誤日誌
        logger.error(f"任務 {job_id} 失敗: {str(e)}\n{traceback.format_exc()}")

        # 發送失敗通知
        send_webhook(
            "job_failed",
            {"job_id": job_id, "error": str(e), "traceback": traceback.format_exc()},
        )

        # 重新拋出異常以便RQ標記任務失敗
        raise

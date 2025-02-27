"""
# src/core/job.py
任務處理模組：定義任務邏輯和處理函數
"""

import os
import time
import logging
import requests  # type: ignore[import-untyped]
import traceback  # type ignore
from typing import Dict, Any, Optional
import subprocess
from rq import get_current_job
from src.config import get_config

logger = logging.getLogger(__name__)


class JobResult:
    """任務結果類"""

    def __init__(
        self,
        model_name: str,
        elapsed_time: float,
        completed_epochs: int,
        metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        self.model_name = model_name
        self.elapsed_time = elapsed_time
        self.completed_epochs = completed_epochs
        self.metrics = metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典用於序列化"""
        return {
            "model": self.model_name,
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


def check_and_pull_image(image_name: str) -> bool:
    """
    檢查本地是否已有 Docker 映像檔，若無則拉取。

    Args:
        image_name (str): Docker Image 名稱

    Returns:
        bool: 是否成功拉取或已存在
    """
    try:
        # 檢查本地是否有該映像檔
        check_command = ["docker", "images", "-q", image_name]
        result = subprocess.run(
            check_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.stdout.strip():
            logger.info(f"✅ 映像檔 `{image_name}` 已存在，跳過拉取")
            return True

        # 如果沒有該映像檔，則執行 `docker pull`
        logger.info(f"⬇️ `{image_name}` 不存在，開始拉取映像檔...")
        pull_command = ["docker", "pull", image_name]
        pull_result = subprocess.run(
            pull_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if pull_result.returncode == 0:
            logger.info(f"✅ 成功拉取 `{image_name}`")
            return True
        else:
            logger.error(
                f"❌ 無法拉取 `{image_name}`，錯誤訊息：\n{pull_result.stderr}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ 檢查或拉取映像檔時發生錯誤: {e}")
        return False


def train_model(image_name: str) -> Dict[str, Any]:
    """
    使用 `docker run` 進行模型訓練，支援動態參數。

    Args:
        image_name (str): Docker Image 名稱

    Returns:
        Dict[str, Any]: 訓練結果
    """
    job = get_current_job()
    job_id = job.id if job else "unknown"

    logger.info(f"🚀 啟動任務 {job_id}，使用 Docker 映像 `{image_name}`")

    # 先確認映像檔是否存在，若無則拉取
    if not check_and_pull_image(image_name):
        logger.error(f"❌ 無法拉取 `{image_name}`，中止訓練")
        send_webhook(
            "job_failed", {"job_id": job_id, "error": f"Failed to pull {image_name}"}
        )
        return {"status": "failed", "error": f"Failed to pull {image_name}"}

    # 構建 `docker run` 指令
    command = [
        "docker",
        "run",
        "--gpus",
        "all",
        "--env-file",
        ".env",
        "--shm-size=16g",
        "--name",
        f"model_training-{job_id}",
        "-v",
        "model_checkpoints:/app/runs/train",
        "-v",
        f"{os.getcwd()}/config.yaml:/app/config.yaml:ro",
        "-v",
        f"{os.getcwd()}/credentials.json:/app/credentials.json:ro",
        "-v",
        f"{os.getcwd()}/.env:/app/.env:ro",
        "-v",
        f"{os.getcwd()}/data/predict:/app/data/predict",
        image_name,
    ]

    logger.info(f"🛠️ 執行指令: {' '.join(command)}")

    start_time = time.time()

    try:
        # 執行 `docker run`
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        completed_epochs = 0

        if process.stdout is not None:
            for line in process.stdout:
                logger.info(f"[{job_id}] {line.strip()}")

                # 檢查是否請求取消
                if job and job.meta.get("cancel_requested", False):
                    logger.warning(f"⛔ 任務 {job_id} 被取消，停止訓練")
                    process.terminate()
                    send_webhook("job_cancelled", {"job_id": job_id})
                    raise InterruptedError("訓練已被取消")

        process.wait()
        elapsed_time = time.time() - start_time
        logger.info(f"✅ 訓練完成，耗時 {elapsed_time:.2f} 秒")

        # 模擬結果
        result = JobResult(
            model_name=image_name,
            elapsed_time=elapsed_time,
            completed_epochs=completed_epochs,
            metrics={"accuracy": 0.95, "loss": 0.05},  # 假設結果
        )

        send_webhook("job_completed", {"job_id": job_id, "result": result.to_dict()})
        return result.to_dict()

    except InterruptedError:
        raise
    except Exception as e:
        logger.error(f"❌ 任務 {job_id} 失敗: {str(e)})")
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        send_webhook("job_failed", {"job_id": job_id, "error": str(e)})
        raise
    finally:
        # 移除 Docker 容器
        if job:
            cmd = ["docker", "rm", f"model_training-{job_id}"]
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                logger.error(
                    f"Remove docker command failed with return code {process.returncode}"
                )

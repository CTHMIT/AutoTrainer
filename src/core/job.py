"""
# src/core/job.py
任務處理模組：定義任務邏輯和處理函數
"""

import time
import logging
import requests  # type: ignore[import-untyped]
import traceback  # type ignore
from typing import Dict, Any, Optional, List
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


def train_model(
    image_name: str,
    gpu_option: str = "all",
    env_file: Optional[str] = ".env",
    shm_size: Optional[str] = "16g",
    volumes: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    使用 `docker run` 進行模型訓練，支援動態參數。

    Args:
        image_name (str): Docker Image 名稱
        gpu_option (str): GPU 設定 ("all" 或 "device=0")
        env_file (str, optional): 環境變數檔案
        shm_size (str, optional): 記憶體大小
        volumes (dict, optional): 映射的 Volume 路徑 { "host_path": "container_path" }

    Returns:
        Dict[str, Any]: 訓練結果
    """
    job = get_current_job()
    job_id = job.id if job else "unknown"

    logger.info(f"🚀 啟動任務 {job_id}，使用 Docker 映像 `{image_name}`")

    # 構建 `docker run` 指令，只加入有提供的參數
    cmd: List[str] = ["docker", "run", "--gpus", gpu_option]

    # 如果有 `env_file`，則加入 `--env-file`
    if env_file:
        cmd.extend(["--env-file", env_file])

    # 如果有 `shm-size`，則加入
    if shm_size:
        cmd.extend(["--shm-size", shm_size])

    # 設定容器名稱
    cmd.extend(["--name", f"training_{job_id}"])

    # 動態加入 Volume 映射
    if volumes:
        for host_path, container_path in volumes.items():
            cmd.extend(["-v", f"{host_path}:{container_path}"])

    # 最後加入 Docker Image
    cmd.append(image_name)

    logger.info(f"🛠️ 執行指令: {' '.join(cmd)}")

    start_time = time.time()

    try:
        # 執行 `docker run`
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # 監控訓練進度
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
        logger.error(f"❌ 任務 {job_id} 失敗: {str(e)}\n{traceback.format_exc()}")
        send_webhook("job_failed", {"job_id": job_id, "error": str(e)})
        raise

"""
# src/api/models.py
API 數據模型：定義API請求與響應的數據結構
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from src.config import Priority


class JobStatus(str, Enum):
    """任務狀態枚舉"""

    QUEUED = "queued"
    STARTED = "started"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainRequest(BaseModel):
    """訓練請求模型"""

    image_name: str = Field(..., min_length=1, description="要訓練的 Docker image 名稱")
    priority: Priority = Field(Priority.MEDIUM, description="任務優先級")
    schedule_time: Optional[str] = Field(None, description="計劃執行時間 (HH:MM 格式)")

    @field_validator("schedule_time")
    def validate_schedule_time(cls, v: Optional[str]) -> Optional[str]:
        """驗證時間格式"""
        if v is None:
            return None

        try:
            # 驗證時間格式 (HH:MM)
            hours, minutes = map(int, v.split(":"))
            if not (0 <= hours < 24 and 0 <= minutes < 60):
                raise ValueError("時間必須在 00:00 到 23:59 之間")
        except Exception:
            raise ValueError("時間格式必須為 'HH:MM'")

        return v


class CancelRequest(BaseModel):
    """取消請求模型"""

    force: bool = Field(False, description="是否強制取消執行中的任務")


class JobResponse(BaseModel):
    """任務響應模型"""

    job_id: str = Field(..., description="任務ID")
    status: JobStatus = Field(..., description="任務狀態")
    priority: Priority = Field(..., description="任務優先級")
    created_at: Optional[datetime] = Field(None, description="創建時間")
    started_at: Optional[datetime] = Field(None, description="開始時間")
    ended_at: Optional[datetime] = Field(None, description="結束時間")
    result: Optional[Dict[str, Any]] = Field(None, description="任務結果")
    error: Optional[str] = Field(None, description="錯誤信息")
    progress: Optional[float] = Field(None, description="進度百分比")


class JobList(BaseModel):
    """任務列表響應模型"""

    jobs: List[JobResponse] = Field(default_factory=list, description="任務列表")
    total: int = Field(..., description="總任務數")


class SystemInfo(BaseModel):
    """系統信息模型"""

    queue_stats: Dict[str, Dict[str, int]] = Field(..., description="隊列統計")
    worker_count: int = Field(..., description="工作器數量")
    version: str = Field(..., description="系統版本")

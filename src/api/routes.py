"""
# src/api/routes.py
API 路由處理：定義FastAPI路由處理函數
"""

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Path, status as http_status

from src.api.models import (
    TrainRequest,
    CancelRequest,
    JobResponse,
    JobList,
    JobStatus,
    SystemInfo,
)
from src.core.queue import get_queue_manager
from src.core.job import train_model
from src.config import Priority

logger = logging.getLogger(__name__)

# 創建路由器
router = APIRouter()


# 輔助函數：轉換任務信息為響應模型
def _convert_job_to_response(job_info: Dict[str, Any]) -> JobResponse:
    """將任務信息轉換為響應模型"""
    # 處理狀態
    try:
        status = JobStatus(job_info.get("status", "queued"))
    except ValueError:
        status = JobStatus.QUEUED

    # 處理優先級
    try:
        priority = Priority(job_info.get("queue", "medium"))
    except ValueError:
        priority = Priority.MEDIUM

    # 創建響應對象
    return JobResponse(
        job_id=job_info["id"],
        status=status,
        priority=priority,
        created_at=job_info.get("created_at"),
        started_at=job_info.get("started_at"),
        ended_at=job_info.get("ended_at"),
        result=job_info.get("result"),
        error=job_info.get("error"),
        progress=job_info.get("progress"),
    )


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="提交新訓練任務",
)
async def submit_job(request: TrainRequest) -> JobResponse:
    """
    提交新的訓練任務到系統

    - **model_name**: 要訓練的模型名稱
    - **epochs**: 訓練輪數 (預設: 10)
    - **priority**: 任務優先級 (high, medium, low)
    - **schedule_time**: 可選的計劃執行時間 (HH:MM 格式)

    返回包含任務ID和初始狀態的信息
    """
    try:
        # 獲取隊列管理器
        queue_manager = get_queue_manager()

        # 入列任務
        job = queue_manager.enqueue(
            train_model, request.model_name, request.epochs, priority=request.priority
        )

        # 構建響應
        return JobResponse(
            job_id=job.id,
            status=JobStatus.QUEUED,
            priority=request.priority,
            created_at=job.created_at,
            started_at=None,
            ended_at=None,
            result=None,
            error=None,
            progress=None,
        )
    except Exception as e:
        logger.error(f"提交任務失敗: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提交任務失敗: {str(e)}",
        )


@router.get("/jobs/{job_id}", response_model=JobResponse, summary="獲取任務狀態")
async def get_job_status(job_id: str = Path(..., description="任務ID")) -> JobResponse:
    """
    獲取特定任務的狀態和詳情

    - **job_id**: 任務的唯一ID

    返回包含狀態、結果(如已完成)和錯誤信息(如失敗)的任務詳情
    """
    # 獲取隊列管理器
    queue_manager = get_queue_manager()

    # 獲取任務
    job = queue_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail=f"找不到任務 {job_id}"
        )

    # 獲取任務資訊
    status_str = job.get_status()

    # 決定狀態對應的JobStatus枚舉
    try:
        job_status = JobStatus(status_str)
    except ValueError:
        job_status = JobStatus.QUEUED

    # 獲取優先級
    queue_name = getattr(job, "origin", "medium")
    try:
        priority = Priority(queue_name)
    except ValueError:
        priority = Priority.MEDIUM

    # 獲取結果或錯誤信息
    result = None
    error = None
    progress = None

    if status_str == "finished":
        result = job.result
    elif status_str == "failed":
        error = str(job.exc_info) if job.exc_info else "未知錯誤"

    # 獲取進度（如有）
    if hasattr(job, "meta") and job.meta:
        progress = job.meta.get("progress")

    # 構建響應
    return JobResponse(
        job_id=job_id,
        status=job_status,
        priority=priority,
        created_at=job.created_at,
        started_at=getattr(job, "started_at", None),
        ended_at=getattr(job, "ended_at", None),
        result=result,
        error=error,
        progress=progress,
    )


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse, summary="取消任務")
async def cancel_job(
    request: CancelRequest, job_id: str = Path(..., description="要取消的任務ID")
) -> JobResponse:
    """
    取消排隊中或執行中的任務

    - **job_id**: 要取消的任務ID
    - **force**: 是否強制取消執行中的任務 (預設: False)

    返回更新後的任務狀態
    """
    # 獲取隊列管理器
    queue_manager = get_queue_manager()

    # 取消任務
    success, message = queue_manager.cancel_job(job_id, force=request.force)
    if not success:
        if message == "任務不存在":
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail=message
            )
        else:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST, detail=message
            )

    # 獲取更新後的任務
    job = queue_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="取消後找不到任務"
        )

    # 設置狀態
    job_status = JobStatus.CANCELLED

    # 獲取優先級
    queue_name = getattr(job, "origin", "medium")
    try:
        priority = Priority(queue_name)
    except ValueError:
        priority = Priority.MEDIUM

    # 構建響應
    return JobResponse(
        job_id=job_id,
        status=job_status,
        priority=priority,
        created_at=job.created_at,
        started_at=getattr(job, "started_at", None),
        ended_at=None,
        result=None,
        error=None,
        progress=None,
    )


@router.get("/jobs", response_model=JobList, summary="列出所有任務")
async def list_jobs(
    status: Optional[str] = Query(
        None, description="按狀態過濾 (queued, started, finished, failed)"
    ),
    priority: Optional[str] = Query(
        None, description="按優先級過濾 (high, medium, low)"
    ),
) -> JobList:
    """
    列出所有任務，可以按狀態和優先級過濾

    - **status**: 可選的狀態過濾器
    - **priority**: 可選的優先級過濾器

    返回任務列表和總數
    """
    # 驗證過濾參數
    if status and status not in [s.value for s in JobStatus]:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,  # Use the imported status
            detail=f"無效的狀態過濾: {status}",
        )

    if priority and priority not in [p.value for p in Priority]:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,  # Use the imported status
            detail=f"無效的優先級過濾: {priority}",
        )

    # 獲取隊列管理器
    queue_manager = get_queue_manager()

    # 獲取任務列表
    jobs_info = queue_manager.list_jobs(status_filter=status)

    # 按優先級過濾
    if priority:
        jobs_info = [j for j in jobs_info if j.get("queue") == priority]

    # 轉換為響應模型
    job_responses = [_convert_job_to_response(job) for job in jobs_info]

    # 構建響應
    return JobList(jobs=job_responses, total=len(job_responses))


@router.get("/system/info", response_model=SystemInfo, summary="獲取系統信息")
async def get_system_info() -> SystemInfo:
    """
    獲取系統狀態和統計信息

    返回包含隊列統計、工作器數量和版本信息的系統狀態
    """
    # 獲取隊列管理器
    queue_manager = get_queue_manager()

    # 獲取配置
    # config = get_config()

    # 獲取任務列表
    jobs_info = queue_manager.list_jobs()

    # 計算隊列統計
    queue_stats = {
        "queued": {"high": 0, "medium": 0, "low": 0, "total": 0},
        "started": {"high": 0, "medium": 0, "low": 0, "total": 0},
        "finished": {"high": 0, "medium": 0, "low": 0, "total": 0},
        "failed": {"high": 0, "medium": 0, "low": 0, "total": 0},
        "total": {"high": 0, "medium": 0, "low": 0, "total": 0},
    }

    for job in jobs_info:
        status = job.get("status", "queued")
        queue = job.get("queue", "medium")

        # 跳過無效的狀態或隊列
        if status not in queue_stats or queue not in queue_stats[status]:
            continue

        # 增加計數
        queue_stats[status][queue] += 1
        queue_stats[status]["total"] += 1
        queue_stats["total"][queue] += 1
        queue_stats["total"]["total"] += 1

    # 構建響應
    return SystemInfo(
        queue_stats=queue_stats,
        worker_count=1,  # 在實際系統中應從Redis檢索工作器數量
        version="0.1.0",  # 實際版本號
    )


@router.get("/health", summary="健康檢查", response_model=dict)
async def health_check() -> dict:
    """健康檢查端點"""
    return {"status": "ok"}

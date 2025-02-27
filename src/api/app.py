"""
# src/api/app.py
FastAPI 應用程序入口點
"""

import logging
import typing
from fastapi import FastAPI, Request, Response
from starlette.types import ASGIApp
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from src.config import get_config

# 獲取日誌器
logger = logging.getLogger(__name__)

# 創建FastAPI應用
app = FastAPI(
    title="AutoTrainer API",
    description="分佈式機器學習訓練管理系統 API",
    version="0.1.0",
)

# 添加CORS中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CallNext = typing.Callable[[Request], typing.Awaitable[ASGIApp]]


# 添加全局請求日誌中間件
@app.middleware("http")
async def log_requests(request: Request, call_next: CallNext) -> Response:
    """記錄所有HTTP請求的中間件"""
    client_host = request.client.host if request.client else "unknown"
    start_time = time.time()

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {client_host} - {process_time:.4f}s"
        )
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"{request.method} {request.url.path} - "
            f"500 - {client_host} - {process_time:.4f}s - 錯誤: {str(e)}"
        )
        return JSONResponse(status_code=500, content={"detail": "內部服務器錯誤"})


@app.get("/")
async def root() -> dict[str, str]:
    """API根路徑"""
    return {"name": "AutoTrainer API", "version": "0.1.0", "documentation": "/docs"}


# 健康檢查端點
@app.get("/health")
async def health_check() -> typing.Dict[str, str]:
    """健康檢查端點"""
    return {"status": "ok"}


# 啟動事件
@app.on_event("startup")
async def startup_event() -> None:
    """應用啟動時的處理函數"""
    config = get_config()
    logger.info(f"API服務啟動於 {config.api.host}:{config.api.port}")
    logger.info(f"Redis連接: {config.redis.host}:{config.redis.port}")


# 關閉事件
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """應用關閉時的處理函數"""
    logger.info("API服務關閉")


# 主入口(直接運行時)
if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "autotrainer.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
    )

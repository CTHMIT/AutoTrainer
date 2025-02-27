"""
命令行介面：提供命令行工具來管理AutoTrainer系統
"""

import os
import sys
import asyncio
import argparse
import logging

from src.config import get_config


def setup_logging(log_level: str) -> None:
    """
    設置日誌記錄

    Args:
        log_level: 日誌級別 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    config = get_config()

    # 更新配置
    config.log.level = log_level

    # 設置日誌級別
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        print(f"無效的日誌級別: {log_level}")
        numeric_level = logging.INFO

    # 配置日誌
    logging.basicConfig(
        level=numeric_level,
        format=config.log.format,
        handlers=[logging.StreamHandler()],
    )


def start_api(args: argparse.Namespace) -> None:
    """
    啟動API伺服器

    Args:
        args: 命令行參數
    """
    import uvicorn

    config = get_config()

    # 更新配置
    if args.host:
        config.api.host = args.host
    if args.port:
        config.api.port = args.port
    if args.redis_host:
        config.redis.host = args.redis_host
    if args.redis_port:
        config.redis.port = args.redis_port
    if args.redis_password:
        config.redis.password = args.redis_password
    if args.webhook:
        config.api.webhook_url = args.webhook

    config.api.debug = args.debug

    # 設置環境變量
    os.environ["API_HOST"] = config.api.host
    os.environ["API_PORT"] = str(config.api.port)
    os.environ["REDIS_HOST"] = config.redis.host
    os.environ["REDIS_PORT"] = str(config.redis.port)
    if config.redis.password:
        os.environ["REDIS_PASSWORD"] = config.redis.password
    if config.api.webhook_url:
        os.environ["WEBHOOK_URL"] = config.api.webhook_url
    os.environ["API_DEBUG"] = "1" if config.api.debug else "0"

    # 啟動API伺服器
    print(f"啟動API伺服器於 {config.api.host}:{config.api.port}")
    uvicorn.run(
        "src.api.app:app",
        host=config.api.host,
        port=config.api.port,
        reload=config.api.debug,
    )


def start_worker(args: argparse.Namespace) -> None:
    """
    啟動Worker進程

    Args:
        args: 命令行參數
    """
    from src.worker.worker import run_worker

    config = get_config()

    # 更新配置
    if args.name:
        config.worker.name = args.name
    if args.redis_host:
        config.redis.host = args.redis_host
    if args.redis_port:
        config.redis.port = args.redis_port
    if args.redis_password:
        config.redis.password = args.redis_password
    if args.queues:
        config.worker.queues = args.queues.split(",")
    if args.retry_limit:
        config.worker.retry_limit = args.retry_limit

    # 設置環境變量
    os.environ["WORKER_NAME"] = config.worker.name
    os.environ["REDIS_HOST"] = config.redis.host
    os.environ["REDIS_PORT"] = str(config.redis.port)
    if config.redis.password:
        os.environ["REDIS_PASSWORD"] = config.redis.password
    os.environ["RETRY_LIMIT"] = str(config.worker.retry_limit)

    # 啟動Worker
    print(f"啟動Worker: {config.worker.name}")
    run_worker()


def start_scheduler(args: argparse.Namespace) -> None:
    """
    啟動調度器

    Args:
        args: 命令行參數
    """
    from src.scheduler.scheduler import run_scheduler

    config = get_config()

    # 更新配置
    if args.redis_host:
        config.redis.host = args.redis_host
    if args.redis_port:
        config.redis.port = args.redis_port
    if args.redis_password:
        config.redis.password = args.redis_password

    # 設置環境變量
    os.environ["REDIS_HOST"] = config.redis.host
    os.environ["REDIS_PORT"] = str(config.redis.port)
    if config.redis.password:
        os.environ["REDIS_PASSWORD"] = config.redis.password

    # 啟動調度器
    print("啟動調度器")
    asyncio.run(run_scheduler())


def main() -> None:
    """主入口函數"""
    parser = argparse.ArgumentParser(
        description="AutoTrainer - 分佈式機器學習訓練管理系統",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # 全局選項
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="日誌級別",
    )
    parser.add_argument("--redis-host", help="Redis主機地址")
    parser.add_argument("--redis-port", type=int, help="Redis端口")
    parser.add_argument("--redis-password", help="Redis密碼")

    # 子命令
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # API命令
    api_parser = subparsers.add_parser("api", help="啟動API伺服器")
    api_parser.add_argument("--host", help="API伺服器主機地址")
    api_parser.add_argument("--port", type=int, help="API伺服器端口")
    api_parser.add_argument("--debug", action="store_true", help="啟用調試模式")
    api_parser.add_argument("--webhook", help="Webhook URL")

    # Worker命令
    worker_parser = subparsers.add_parser("worker", help="啟動Worker進程")
    worker_parser.add_argument("--name", help="Worker名稱")
    worker_parser.add_argument("--queues", help="要處理的隊列（逗號分隔）")
    worker_parser.add_argument("--retry-limit", type=int, help="任務重試次數限制")

    # 調度器命令
    # scheduler_parser = subparsers.add_parser("scheduler", help="啟動調度器")

    # 解析參數
    args = parser.parse_args()

    # 設置日誌
    setup_logging(args.log_level)

    # 執行命令
    if args.command == "api":
        start_api(args)
    elif args.command == "worker":
        start_worker(args)
    elif args.command == "scheduler":
        start_scheduler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

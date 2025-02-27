#!/usr/bin/env python3
"""
AutoTrainer 啟動腳本

使用範例:
    # 啟動 API 伺服器
    python run.py api

    # 啟動 Worker 進程
    python run.py worker

    # 啟動調度器
    python run.py scheduler

    # 顯示幫助信息
    python run.py --help
"""
from src.cli import main

if __name__ == "__main__":
    main()

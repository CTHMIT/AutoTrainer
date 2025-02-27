用戶 API 請求 ---> FastAPI 服務 (/train, /status 等)
    |                   |
    | 提交任務           | 查詢/取消
    v                   v
  任務加入 Redis <-- 任務狀態查詢
    (高/中/低優先佇列)      (從 Redis 獲取狀態)
    |
    v
調度器 (Scheduler) 監控 GPU/CPU 資源並決定啟動任務
    |
    v
工作進程 (Worker) 執行深度學習訓練程式 (記錄日誌, 上報監控, Webhook)
    |
    v
更新任務狀態至 Redis (queued->running->finished/failed)


AutoTrainer/
├── pyproject.toml           # 專案定義與依賴
├── README.md                # 專案文檔
├── run.py                   # 主要啟動腳本
├── Dockerfile               # 容器化配置
├── docker-compose.yml       # 多容器部署配置
├── .github/                 # CI/CD配置
│   └── workflows/
│       └── tests.yml        # 自動化測試流程
│
├── src/                     # 主套件
│   ├── __init__.py          # 套件初始化
│   ├── config.py            # 中央配置
│   ├── cli.py               # 命令行介面
│   │
│   ├── api/                 # API服務
│   │   ├── __init__.py
│   │   ├── app.py           # FastAPI應用
│   │   ├── models.py        # 數據模型
│   │   └── routes.py        # 路由處理
│   │
│   ├── core/                # 核心邏輯
│   │   ├── __init__.py
│   │   ├── queue.py         # 隊列管理
│   │   └── job.py           # 任務管理
│   │
│   ├── worker/              # Worker處理
│   │   ├── __init__.py
│   │   └── worker.py        # Worker實現
│   │
│   ├── scheduler/           # 任務調度
│   │   ├── __init__.py
│   │   └── scheduler.py     # 調度器實現
│   │
│   └── utils/               # 工具函數
│       ├── __init__.py
│       ├── logging.py       # 日誌工具
│       └── monitoring.py    # 監控工具
│
└── tests/                   # 測試模組
    ├── __init__.py
    ├── conftest.py          # 測試配置
    ├── unit/                # 單元測試
    │   ├── __init__.py
    │   ├── test_config.py   # 配置測試
    │   ├── test_core.py     # 核心邏輯測試
    │   └── test_cli.py      # CLI測試
    │
    ├── integration/         # 整合測試
    │   ├── __init__.py
    │   └── test_workflow.py # 工作流程測試
    │
    └── e2e/                 # 端到端測試
        ├── __init__.py
        ├── docker-compose.test.yml # 測試環境配置
        └── test_system.py   # 系統測試

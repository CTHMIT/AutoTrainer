# AutoTrainer

分佈式機器學習訓練管理系統，提供優先級排序、資源監控和任務調度功能。

## 功能特點

- **優先級隊列**: 高、中、低優先級的訓練任務排序
- **資源監控**: 監控 CPU、記憶體和 GPU 資源使用情況
- **分佈式架構**: 支援多 Worker 水平擴展
- **RESTful API**: 易於整合到現有的機器學習工作流
- **任務狀態追蹤**: 監控訓練進度和結果
- **Webhook 通知**: 訓練完成或失敗時的自動通知

## 系統架構

系統由以下幾個主要組件組成：

- **API 服務器**: 處理 HTTP 請求，管理任務提交和查詢
- **Redis**: 用於任務佇列和元數據儲存
- **Worker**: 執行訓練任務的處理程序
- **調度器**: 監控系統資源並調度任務執行

## 快速開始

### 使用 Docker Compose

最簡單的方式是使用 Docker Compose 啟動整個系統：

```bash
# 啟動所有服務
docker compose up -d

# 查看日誌
docker compose logs -f

# 停止服務
docker compose down
```

### 本地開發

安裝依賴：

```bash
# 使用 PDM 安裝依賴
pdm install
```

啟動 Redis（或使用遠端 Redis）：

```bash
docker run -d -p 6379:6379 redis:alpine
```

啟動各組件：

```bash
# 啟動 API 服務器
pdm run start

# 啟動 Worker
pdm run worker

# 啟動調度器
pdm run scheduler
```

## API 使用範例

### 提交訓練任務

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "resnet50",
    "epochs": 10,
    "priority": "high"
  }'
```

### 查詢任務狀態

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}
```

### 取消任務

```bash
curl -X POST http://localhost:8000/api/v1/jobs/{job_id}/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "force": true
  }'
```

### 列出所有任務

```bash
curl http://localhost:8000/api/v1/jobs
```

## 專案結構

```
autotrainer/
├── autotrainer/             # 主套件
│   ├── api/                 # API 服務
│   ├── core/                # 核心邏輯
│   ├── worker/              # Worker 處理
│   ├── scheduler/           # 任務調度
│   └── utils/               # 工具函數
├── tests/                   # 測試目錄
├── docker-compose.yml       # Docker 配置
├── Dockerfile               # 容器化配置
├── pyproject.toml           # 專案定義
└── run.py                   # 主要啟動腳本
```

## 開發指南

### 運行測試

```bash
# 運行單元測試
pdm run test

# 計算測試覆蓋率
pdm run coverage
```

### 程式碼風格

```bash
# 檢查程式碼風格
pdm run lint

# 運行類型檢查
pdm run mypy

# 格式化程式碼
pdm run format
```

## 貢獻

歡迎貢獻! 請先 fork 這個倉庫，創建您的功能分支，提交更改後發起 Pull Request。

## 許可協議

MIT

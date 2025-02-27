# 使用較輕量的 Python 3.11 slim 版本
FROM python:3.11-slim

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PDM_VENV_IN_PROJECT=1 \
    XDG_CACHE_HOME="/app/.cache" \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"

# 安裝必要的系統工具（最小化安裝）
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

# 安裝 PDM
RUN pip install --no-cache-dir pdm==2.11.1

# 設定工作目錄
WORKDIR /app

# 創建非 root 用戶（避免 `chown: invalid user` 問題）
RUN addgroup --system app && adduser --system --group app

# 創建必要目錄並調整權限
RUN mkdir -p /app/.venv /app/.cache /app/logs && \
    chown -R app:app /app

# 切換為非 root 用戶
USER app

# 複製 PDM 設定檔案
COPY --chown=app:app pyproject.toml pdm.lock* README.md /app/

# 安裝正式環境依賴（確保 `.venv` 屬於 `app`）
RUN pdm install --prod

# 複製應用程式代碼
COPY --chown=app:app src /app/src/

# 確保 `logs` 目錄可寫
RUN chmod 777 /app/logs

# 暴露 API 端口（適用於 `api` container）
EXPOSE 8000

# 設定 entrypoint
ENTRYPOINT ["pdm", "run"]

# 預設為 API 服務（其他 container 會在 `compose.yaml` 內覆寫 CMD）
CMD ["python", "-m", "src.api.app"]

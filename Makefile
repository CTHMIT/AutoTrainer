install:
	pdm install

build:
	docker compose build --no-cache

run:
	docker-compose up --build

# 後台啟動所有服務
up: build
	docker compose up -d

# 停止並移除容器
down:
	docker compose down

clean:
	docker compose down -v
	rm -rf __pycache__ .pytest_cache

# 實時查看日誌
logs:
	docker compose logs -f

# 重啟服務
restart:
	docker compose down && docker-compose up -d

# 運行單元測試
test-unit:
	pytest tests/unit -v

# 運行整合測試
test-integration:
	pytest tests/integration -v

# 運行端到端測試
test-e2e:
	cd tests/e2e && docker-compose -f docker-compose.test.yml up -d
	sleep 10  # 等待容器啟動
	pytest tests/e2e -v -m e2e
	cd tests/e2e && docker-compose -f docker-compose.test.yml down

# 運行效能測試
test-performance:
	pytest tests/performance -v -m performance

# 運行所有測試
test-all: test-unit test-integration test-e2e test-performance

# 安裝測試依賴
setup-test:
	pdm install -G test

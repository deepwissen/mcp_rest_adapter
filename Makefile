# Makefile for MCPAdapters project

.PHONY: help install test test-unit test-integration test-coverage lint type-check security clean docker-up docker-down

# Default target
help:
	@echo "MCPAdapters Development Commands"
	@echo "================================"
	@echo "install          Install project dependencies"
	@echo "test             Run all tests"
	@echo "test-unit        Run unit tests only"
	@echo "test-integration Run integration tests only"
	@echo "test-coverage    Run tests with coverage report"
	@echo "lint             Run code linting"
	@echo "type-check       Run type checking"
	@echo "security         Run security scans"
	@echo "clean            Clean up generated files"
	@echo "docker-up        Start mock services with Docker"
	@echo "docker-down      Stop mock services"
	@echo "dev              Set up development environment"
	@echo "check-all        Run all checks (lint, type-check, test, security)"

# Install dependencies
install:
	pip install -r requirements.txt

# Development setup
dev: install
	pre-commit install || echo "pre-commit not available"

# Run all tests
test:
	python run_tests.py

# Run unit tests
test-unit:
	python run_tests.py --unit

# Run integration tests
test-integration:
	python run_tests.py --integration

# Run tests with coverage
test-coverage:
	python run_tests.py --coverage

# Run linting
lint:
	python run_tests.py --lint

# Run type checking
type-check:
	python run_tests.py --type-check

# Run security scans
security:
	python run_tests.py --security

# Run all checks
check-all:
	python run_tests.py --all

# Clean up generated files
clean:
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf bandit-report.json
	rm -rf .mypy_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Docker commands
docker-up:
	docker-compose up -d
	@echo "Waiting for services to be ready..."
	@sleep 10
	@echo "Services should be ready at:"
	@echo "  Customer API: http://localhost:8001"
	@echo "  Order API: http://localhost:8002"
	@echo "  Inventory API: http://localhost:8003"

docker-down:
	docker-compose down

# Quick health check
health-check:
	@echo "Checking service health..."
	@curl -s http://localhost:8001/health | jq . || echo "Customer service not available"
	@curl -s http://localhost:8002/health | jq . || echo "Order service not available"
	@curl -s http://localhost:8003/health | jq . || echo "Inventory service not available"

# Run MCP adapter locally
run-mcp:
	cd mcp_adapter && python server.py

# Run mock services locally (in background)
run-services:
	cd mock-services && python mock_customer_service.py &
	cd mock-services && python mock_order_service.py &
	cd mock-services && python mock_inventory_service.py &
	@echo "Mock services started in background"

# Stop background services
stop-services:
	pkill -f mock_customer_service.py || true
	pkill -f mock_order_service.py || true
	pkill -f mock_inventory_service.py || true
	@echo "Mock services stopped"

# Format code
format:
	black mcp_adapter/ mock-services/ tests/ --line-length 100
	isort mcp_adapter/ mock-services/ tests/

# Check code formatting
format-check:
	black --check mcp_adapter/ mock-services/ tests/ --line-length 100
	isort --check-only mcp_adapter/ mock-services/ tests/

# Generate documentation
docs:
	@echo "Generating documentation..."
	@echo "API documentation available at:"
	@echo "  Customer API: http://localhost:8001/docs"
	@echo "  Order API: http://localhost:8002/docs"
	@echo "  Inventory API: http://localhost:8003/docs"

# Performance tests (placeholder)
test-performance:
	@echo "Performance tests not implemented yet"

# Benchmark tests (placeholder)
test-benchmark:
	@echo "Benchmark tests not implemented yet"
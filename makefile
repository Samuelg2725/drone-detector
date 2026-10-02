.PHONY: help install run test lint docker-clean

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make run         - Run the application"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linters"
	@echo "  make docker-up   - Start Docker containers"
	@echo "  make docker-down - Stop Docker containers"
	@echo "  make clean       - Clean temporary files"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

run:
	python run.py

test:
	pytest tests/ -v --cov=. --cov-report=html

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	ruff check .
	black --check .
	mypy .

format:
	black .
	ruff check --fix .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-build:
	docker-compose build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.log" -delete
	rm -rf .pytest_cache .coverage htmlcov
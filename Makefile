# Makefile for Dynamic Orchestrator MCP

.PHONY: help install dev test lint format clean run-local run-podman build-podman

# Variables
PROJECT_NAME = dynamic-orchestrator-mcp
PYTHON_VERSION = 3.11
PODMAN_IMAGE = $(PROJECT_NAME):latest
PODMAN_REGISTRY = localhost

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies with uv"
	@echo "  make dev          - Install dev dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean temporary files"
	@echo "  make run-local    - Run MCP server locally"
	@echo "  make run-podman   - Run MCP server in Podman"
	@echo "  make build-podman - Build Podman image"

# Install dependencies with uv
install:
	@echo "Installing dependencies with uv..."
	uv pip sync requirements.txt
	uv pip install -e .

# Install dev dependencies
dev:
	@echo "Installing dev dependencies..."
	uv pip install -r requirements-dev.txt

# Run tests
test:
	@echo "Running tests..."
	uv run pytest tests/ -v --cov=src --cov-report=html

# Lint code
lint:
	@echo "Running linters..."
	uv run ruff check src/
	uv run mypy src/

# Format code
format:
	@echo "Formatting code..."
	uv run black src/ tests/
	uv run ruff check --fix src/

# Clean temporary files
clean:
	@echo "Cleaning temporary files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .coverage htmlcov .mypy_cache
	rm -rf build dist *.egg-info

# Run locally with uv
run-local:
	@echo "Starting MCP server locally..."
	uv run python src/server.py

# Build Podman image
build-podman:
	@echo "Building Podman image..."
	podman build -t $(PODMAN_IMAGE) -f Containerfile .

# Run in Podman container
run-podman: build-podman
	@echo "Running MCP server in Podman..."
	podman run --rm -it \
		--name $(PROJECT_NAME) \
		-e OPENAI_API_KEY=$${OPENAI_API_KEY} \
		-e GOOGLE_API_KEY=$${GOOGLE_API_KEY} \
		-e ANTHROPIC_API_KEY=$${ANTHROPIC_API_KEY} \
		-v ./config:/app/config:ro \
		-p 8080:8080 \
		$(PODMAN_IMAGE)

# Run Podman with Redis
run-podman-full:
	@echo "Starting full stack with Podman Compose..."
	podman-compose -f podman-compose.yml up

# Stop Podman services
stop-podman:
	@echo "Stopping Podman services..."
	podman-compose -f podman-compose.yml down

# Development mode with hot reload
dev-server:
	@echo "Starting development server with hot reload..."
	uv run watchdog src/ --command='python src/server.py'

# Initialize project
init:
	@echo "Initializing project..."
	@command -v uv >/dev/null 2>&1 || { echo "Installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; }
	uv venv
	$(MAKE) install
	$(MAKE) dev
	@echo "Project initialized successfully!"
#!/bin/bash

# Development helper script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env exists
if [ ! -f ".env" ]; then
    print_warn ".env file not found. Creating from template..."
    cp .env.example .env
    print_info "Please edit .env and add your API keys"
    exit 1
fi

# Parse command
COMMAND=${1:-help}

case $COMMAND in
    start)
        print_info "Starting development environment with Podman..."
        podman-compose -f podman-compose.dev.yml up
        ;;
    
    stop)
        print_info "Stopping development environment..."
        podman-compose -f podman-compose.dev.yml down
        ;;
    
    restart)
        print_info "Restarting development environment..."
        podman-compose -f podman-compose.dev.yml restart
        ;;
    
    logs)
        SERVICE=${2:-orchestrator-dev}
        print_info "Showing logs for $SERVICE..."
        podman-compose -f podman-compose.dev.yml logs -f $SERVICE
        ;;
    
    shell)
        print_info "Opening shell in orchestrator container..."
        podman exec -it dynamic-orchestrator-mcp-dev bash
        ;;
    
    test)
        print_info "Running tests in container..."
        podman exec -it dynamic-orchestrator-mcp-dev pytest tests/ -v
        ;;
    
    lint)
        print_info "Running linters..."
        podman exec -it dynamic-orchestrator-mcp-dev bash -c "ruff check src/ && mypy src/"
        ;;
    
    format)
        print_info "Formatting code..."
        podman exec -it dynamic-orchestrator-mcp-dev bash -c "black src/ tests/ && ruff check --fix src/"
        ;;
    
    redis-cli)
        print_info "Opening Redis CLI..."
        podman exec -it orchestrator-redis-dev redis-cli
        ;;
    
    build)
        print_info "Building development container..."
        podman build -t dynamic-orchestrator-mcp:dev -f Containerfile.dev .
        ;;
    
    clean)
        print_info "Cleaning up containers and volumes..."
        podman-compose -f podman-compose.dev.yml down -v
        ;;
    
    help|*)
        echo "Dynamic Orchestrator MCP - Development Helper"
        echo ""
        echo "Usage: ./scripts/dev.sh [command]"
        echo ""
        echo "Commands:"
        echo "  start       - Start development environment"
        echo "  stop        - Stop development environment"
        echo "  restart     - Restart development environment"
        echo "  logs [svc]  - Show logs (default: orchestrator-dev)"
        echo "  shell       - Open shell in orchestrator container"
        echo "  test        - Run tests in container"
        echo "  lint        - Run linters"
        echo "  format      - Format code"
        echo "  redis-cli   - Open Redis CLI"
        echo "  build       - Build development container"
        echo "  clean       - Clean up containers and volumes"
        echo "  help        - Show this help message"
        ;;
esac
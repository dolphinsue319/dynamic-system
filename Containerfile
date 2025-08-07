# Multi-stage build for Dynamic Orchestrator MCP
# Stage 1: Builder
FROM python:3.11-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml requirements.txt requirements-dev.txt ./

# Create virtual environment and install dependencies
RUN uv venv .venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies
RUN uv pip install --no-cache -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Install runtime dependencies (minimal - no nodejs/npm needed for Python MCP)
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 mcp && \
    mkdir -p /app && \
    chown -R mcp:mcp /app

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=mcp:mcp /app/.venv /app/.venv

# Set environment variables
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application code
COPY --chown=mcp:mcp src/ ./src/
COPY --chown=mcp:mcp config/ ./config/

# Create directories for runtime
RUN mkdir -p /app/logs /app/data && \
    chown -R mcp:mcp /app/logs /app/data

# Switch to non-root user
USER mcp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Environment variables (can be overridden at runtime)
ENV LOG_LEVEL=INFO
ENV CACHE_TTL=3600
ENV MCP_PORT=8080

# Expose MCP port
EXPOSE 8080

# Run the MCP server
CMD ["python", "src/server.py"]
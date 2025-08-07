#!/bin/bash

# Setup script for Dynamic Orchestrator MCP

set -e

echo "==================================="
echo "Dynamic Orchestrator MCP Setup"
echo "==================================="

# Check for required tools
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 is not installed"
        return 1
    else
        echo "✅ $1 is installed"
        return 0
    fi
}

echo ""
echo "Checking required tools..."
echo "--------------------------"

MISSING_TOOLS=0

# Check Python
if check_command python3; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    echo "   Python version: $PYTHON_VERSION"
else
    MISSING_TOOLS=1
fi

# Check uv
if ! check_command uv; then
    echo ""
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    echo "✅ uv installed"
fi

# Check Podman
if check_command podman; then
    PODMAN_VERSION=$(podman --version | cut -d' ' -f3)
    echo "   Podman version: $PODMAN_VERSION"
else
    echo "   ⚠️  Podman is optional but recommended for containerization"
fi

# Check podman-compose
if ! check_command podman-compose; then
    if check_command pip3; then
        echo ""
        echo "Installing podman-compose..."
        pip3 install --user podman-compose
        echo "✅ podman-compose installed"
    fi
fi

if [ $MISSING_TOOLS -eq 1 ]; then
    echo ""
    echo "❌ Some required tools are missing. Please install them first."
    exit 1
fi

echo ""
echo "Setting up Python environment..."
echo "---------------------------------"

# Create virtual environment with uv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
    echo "✅ Virtual environment created"
else
    echo "✅ Virtual environment already exists"
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
echo "✅ Dependencies installed"

# Setup configuration
echo ""
echo "Setting up configuration..."
echo "---------------------------"

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ Created .env file from template"
    echo "   ⚠️  Please edit .env and add your API keys"
else
    echo "✅ .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p logs data monitoring/prometheus monitoring/grafana/dashboards monitoring/grafana/datasources
echo "✅ Directories created"

# Setup git hooks (optional)
if [ -d ".git" ]; then
    echo ""
    echo "Setting up git hooks..."
    cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
source .venv/bin/activate
make lint
EOF
    chmod +x .git/hooks/pre-commit
    echo "✅ Git hooks configured"
fi

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file and add your API keys"
echo "2. Run 'make run-local' to start the server locally"
echo "3. Run 'make build-podman' to build the container"
echo "4. Run 'make run-podman-full' to start with all services"
echo ""
echo "For more commands, run: make help"
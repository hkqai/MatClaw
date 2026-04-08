#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# MatClaw MCP — environment setup
#
# Usage:
#   bash setup.sh
#
# Supports: Linux, macOS, Windows (Git Bash/WSL).
# ---------------------------------------------------------------------------
set -euo pipefail

# Detect OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
  IS_WINDOWS=true
else
  IS_WINDOWS=false
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# 0. Python version check
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking Python version..."

PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

echo "    Detected: Python $PYTHON_VERSION"

if [[ "$PYTHON_MAJOR" -ne 3 ]] || { [[ "$PYTHON_MINOR" -ne 10 ]] && [[ "$PYTHON_MINOR" -ne 11 ]]; }; then
  echo ""
  echo "    ERROR: Python 3.10 or 3.11 is required."
  echo "    You are using Python $PYTHON_VERSION."
  echo ""
  echo "    Please install Python 3.10 or 3.11 and ensure it is available as 'python'."
  echo "    Alternatively, use 'python3.10' or 'python3.11' explicitly and modify this script."
  exit 1
fi

echo "      Python version is compatible."

# ---------------------------------------------------------------------------
# 1. Python venv
# ---------------------------------------------------------------------------
echo ""
echo "==> Setting up Python virtual environment..."

if [[ ! -d "venv" ]]; then
  python -m venv venv
  echo "    Created venv."
else
  echo "    venv already exists — skipping creation."
fi

# Activate venv (OS-specific path)
if [[ "$IS_WINDOWS" == true ]]; then
  source venv/Scripts/activate
else
  source venv/bin/activate
fi

# ---------------------------------------------------------------------------
# 2. Pip dependencies
# ---------------------------------------------------------------------------
echo ""
echo "==> Installing pip dependencies from requirements.txt..."
python -m pip install --upgrade pip --quiet --disable-pip-version-check
python -m pip install -r requirements.txt
echo "    Done."

# ---------------------------------------------------------------------------
# 2.5. PyTorch Scatter (CUDA-aware installation)
# ---------------------------------------------------------------------------
echo ""
echo "==> Detecting CUDA and installing torch-scatter..."

# Detect CUDA availability and version via PyTorch
CUDA_INFO=$(python -c "
import torch
import sys
if torch.cuda.is_available():
    cuda_version = torch.version.cuda
    # Convert CUDA version to PyG wheel format (e.g., '11.8' -> 'cu118', '12.1' -> 'cu121')
    if cuda_version:
        major, minor = cuda_version.split('.')
        print(f'cu{major}{minor}')
    else:
        print('cpu')
else:
    print('cpu')
" 2>/dev/null || echo "cpu")

echo "    Detected: $CUDA_INFO"

# Determine PyTorch version for wheel compatibility
TORCH_VERSION=$(python -c "import torch; print(torch.__version__.split('+')[0])" 2>/dev/null || echo "2.2.1")

# Install torch-scatter with appropriate wheel
WHEEL_URL="https://data.pyg.org/whl/torch-${TORCH_VERSION}+${CUDA_INFO}.html"
echo "    Installing torch-scatter from: $WHEEL_URL"

python -m pip install torch-scatter -f "$WHEEL_URL" --no-cache-dir

if python -c "import torch_scatter" 2>/dev/null; then
  echo "    torch-scatter installed successfully."
else
  echo ""
  echo "    WARNING: torch-scatter installation may have failed."
  echo "    This is required for elemwise_retro tools."
  echo "    Try manually: pip install torch-scatter -f $WHEEL_URL"
fi

# ---------------------------------------------------------------------------
# 3. .env file
# ---------------------------------------------------------------------------
echo ""
if [[ ! -f ".env" ]]; then
  cp .env.example .env
  echo "==> Created .env from .env.example."
  echo "    *** Set your MP_API_KEY in mcp/.env before running the server. ***"
else
  echo "==> .env already exists — skipping."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==> Setup complete."
echo ""
if [[ "$IS_WINDOWS" == true ]]; then
  echo "    Activate the venv with:   source venv/Scripts/activate"
else
  echo "    Activate the venv with:   source venv/bin/activate"
fi
echo "    Run the server with:      python server.py"
echo "    Run tests with:           python -m pytest tests/ -v"
echo ""

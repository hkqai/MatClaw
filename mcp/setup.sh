#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# MatClaw MCP — environment setup
#
# Usage:
#   bash setup.sh            # full setup (venv + pip + enumlib check)
#   bash setup.sh --no-enum  # skip enumlib installation
#
# Supports: Linux, macOS, Windows (Git Bash/WSL).
# Note: enumlib installation requires conda or WSL on Windows.
# ---------------------------------------------------------------------------
set -euo pipefail

# Detect OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
  IS_WINDOWS=true
else
  IS_WINDOWS=false
fi

SKIP_ENUM=false
for arg in "$@"; do
  [[ "$arg" == "--no-enum" ]] && SKIP_ENUM=true
done

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
# 4. enumlib (enum.x)  — Linux/macOS via conda, Windows via WSL
# ---------------------------------------------------------------------------
if [[ "$SKIP_ENUM" == true ]]; then
  echo ""
  echo "==> Skipping enumlib installation (--no-enum)."
else
  echo ""
  echo "==> Checking for enumlib (enum.x)..."

  if command -v enum.x &>/dev/null; then
    echo "    enum.x found at: $(command -v enum.x)"
    echo "    EnumerateStructureTransformation (pymatgen_enumeration_generator) is available."
  else
    echo "    enum.x not found on PATH."

    if command -v conda &>/dev/null; then
      echo "    conda found — installing enumlib from conda-forge..."
      # Install into the base/active conda env so enum.x lands on PATH
      conda install -c conda-forge enumlib -y
      if command -v enum.x &>/dev/null; then
        echo "    enum.x installed successfully at: $(command -v enum.x)"
      else
        echo ""
        echo "    WARNING: conda install completed but enum.x is still not on PATH."
        echo "    You may need to restart your shell or activate the correct conda env,"
        echo "    then re-run: conda install -c conda-forge enumlib"
      fi
    else
      echo ""
      echo "    WARNING: conda not found — cannot install enumlib automatically."
      echo ""
      echo "    To install enumlib manually:"
      echo "      Linux/macOS:  conda install -c conda-forge enumlib"
      echo "      Windows:      Run this script inside WSL (wsl --install Ubuntu)"
      echo ""
      echo "    The MCP server will still start and all tools except"
      echo "    pymatgen_enumeration_generator will work normally."
    fi
  fi
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

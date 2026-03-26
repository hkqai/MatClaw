#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# MatClaw MCP — environment setup
#
# Usage:
#   bash setup.sh            # full setup (venv + pip + enumlib check)
#   bash setup.sh --no-enum  # skip enumlib installation
#
# Supports: Linux, macOS, Windows WSL.
# Does NOT run natively on Windows CMD/PowerShell — use WSL for enumlib.
# ---------------------------------------------------------------------------
set -euo pipefail

SKIP_ENUM=false
for arg in "$@"; do
  [[ "$arg" == "--no-enum" ]] && SKIP_ENUM=true
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

# Activate
source venv/bin/activate

# ---------------------------------------------------------------------------
# 2. Pip dependencies
# ---------------------------------------------------------------------------
echo ""
echo "==> Installing pip dependencies from requirements.txt..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
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
echo "    Activate the venv with:   source venv/bin/activate"
echo "    Run the server with:      python server.py"
echo "    Run tests with:           python -m pytest tests/ -v"
echo ""

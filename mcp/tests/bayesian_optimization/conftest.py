"""
Pytest configuration for Bayesian Optimization tests.
"""

import pytest
import sys
from pathlib import Path

# Add the tools directory to Python path for imports
tools_dir = Path(__file__).parent.parent.parent / "tools"
sys.path.insert(0, str(tools_dir))

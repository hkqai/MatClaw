"""
Active learning tools test fixtures.
"""

import pytest
import os


# Materials Project API key fixtures
@pytest.fixture
def mp_api_key():
    """Materials Project API key from environment variable.

    Classes decorated with @pytest.mark.usefixtures("mp_api_key") will be
    automatically skipped when MP_API_KEY is not set in the environment.
    """
    api_key = os.environ.get("MP_API_KEY")
    if not api_key:
        pytest.skip("MP_API_KEY environment variable not set")
    return api_key


@pytest.fixture
def mp_api_key_available():
    """Check if Materials Project API key is available."""
    return bool(os.environ.get("MP_API_KEY"))

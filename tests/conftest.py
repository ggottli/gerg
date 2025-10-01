# conftest.py
# Shared pytest configuration and fixtures for gerg tests.

import sys
import pathlib
import pytest

# Ensure the gerg package root is on sys.path for test discovery
PACKAGE_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))


@pytest.fixture(scope="session")
def sample_goal() -> str:
    """Provide a sample natural-language goal for tests."""
    return "echo hello world"


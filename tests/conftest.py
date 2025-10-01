# conftest.py
# Shared pytest configuration and fixtures for gerg tests.

import pytest


@pytest.fixture(scope="session")
def sample_goal() -> str:
    """Provide a sample natural-language goal for tests."""
    return "echo hello world"

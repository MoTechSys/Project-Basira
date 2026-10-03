"""Pytest fixtures shared across all tests."""
from __future__ import annotations

import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    """Test settings with mock providers (no network, no cost)."""
    return Settings(
        llm_provider="mock",
        vision_provider="mock",
        rate_limit=1000,  # relaxed for tests
    )

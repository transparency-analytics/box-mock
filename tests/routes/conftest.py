"""Fixtures for route tests."""

import pytest

from app import create_app


@pytest.fixture
def client():
    """Create a test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client

"""Fixtures for route tests."""

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient

from app import create_app


@pytest.fixture
def client() -> Iterator[FlaskClient]:
    """Yield a Flask test client backed by a fresh in-memory SQLite database.

    Each call to create_app(testing=True) generates a unique database URL, so
    tests are isolated without any monkeypatching or filesystem access.
    """
    app = create_app(testing=True)
    with app.test_client() as test_client:
        yield test_client

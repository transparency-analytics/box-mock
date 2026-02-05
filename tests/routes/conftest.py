"""Fixtures for route tests."""

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient

from app import create_app


@pytest.fixture
def client() -> Iterator[FlaskClient]:
    """Yield a Flask test client."""
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client

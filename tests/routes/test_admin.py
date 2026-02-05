"""Tests for admin routes."""

from unittest.mock import MagicMock, patch

from flask.testing import FlaskClient


@patch("box_mock.routes.admin.reset_identity_data")
def test_reset_calls_reset_identity_data(
    mock_reset: MagicMock,
    client: FlaskClient,
):
    """Test that POST /_reset calls reset_identity_data with correct identity."""
    response = client.post(
        "/_reset",
        json={"identity": "test-worker"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json == {"status": "reset complete", "identity": "test-worker"}
    mock_reset.assert_called_once_with("test-worker")


def test_browse_returns_html(client: FlaskClient):
    """Test that GET /_browse returns HTML page."""
    response = client.get("/_browse")

    assert response.status_code == 200
    assert b"Box Mock Browser" in response.data


def test_health_returns_ok(client: FlaskClient):
    """Test that GET /health returns ok status."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}

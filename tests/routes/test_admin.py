"""Tests for admin routes."""

from unittest.mock import patch


@patch("box_mock.routes.admin.reset_identity_data")
def test_reset_calls_reset_identity_data(mock_reset, client):
    """Test that POST /_reset calls reset_identity_data with correct identity."""
    response = client.post(
        "/_reset",
        json={"identity": "test-worker"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json == {"status": "reset complete", "identity": "test-worker"}
    mock_reset.assert_called_once_with("test-worker")

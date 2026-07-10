"""Tests for admin routes."""

from pathlib import Path
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
    assert b"Mock dev" in response.data


@patch("box_mock.routes.admin._get_identity_data")
def test_browse_shows_download_link(
    mock_identity_data: MagicMock,
    client: FlaskClient,
    tmp_path: Path,
):
    """Files on /_browse link to the download endpoint with identity embedded."""
    identity_dir = tmp_path / "browse-ident"
    identity_dir.mkdir()
    (identity_dir / "box.db").touch()
    mock_identity_data.return_value = {
        "name": "browse-ident",
        "tree": {
            "id": "0",
            "name": "All Files",
            "files": [{"id": "file-1", "name": "hello.txt", "size": 22}],
            "children": [],
        },
        "users": [],
        "groups": [],
        "sign_requests": [],
    }

    with patch("box_mock.routes.admin.DATA_DIR", tmp_path):
        response = client.get("/_browse")

    assert response.status_code == 200
    href = "/2.0/files/file-1/content?access_token=Identity%3Dbrowse-ident"
    assert href.encode() in response.data
    assert b"(file-1, 22 bytes)" in response.data


def test_health_returns_ok(client: FlaskClient):
    """Test that GET /health returns ok status."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}

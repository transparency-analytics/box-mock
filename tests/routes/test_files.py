"""Tests for file routes."""

import io
import json

from flask.testing import FlaskClient
from werkzeug.test import TestResponse


def _upload_file(
    client: FlaskClient,
    name: str = "test.txt",
    content: bytes = b"test content",
    parent_id: str = "0",
) -> TestResponse:
    """Upload a file for testing."""
    return client.post(
        "/2.0/files/content",
        data={
            "attributes": json.dumps({"name": name, "parent": {"id": parent_id}}),
            "file": (io.BytesIO(content), name),
        },
        content_type="multipart/form-data",
    )


def test_upload_file(client: FlaskClient):
    """Test that POST /2.0/files/content uploads a file."""
    response = _upload_file(client)

    assert response.status_code == 201
    data = response.json
    assert "entries" in data
    assert len(data["entries"]) == 1
    assert data["entries"][0]["name"] == "test.txt"


def test_get_file(client: FlaskClient):
    """Test that GET /2.0/files/<id> returns file metadata."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.get(f"/2.0/files/{file_id}")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "file"
    assert data["id"] == file_id


def test_update_file(client: FlaskClient):
    """Test that PUT /2.0/files/<id> updates file metadata."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.put(
        f"/2.0/files/{file_id}",
        json={"name": "renamed.txt"},
    )

    assert response.status_code == 200
    assert response.json["name"] == "renamed.txt"


def test_delete_file(client: FlaskClient):
    """Test that DELETE /2.0/files/<id> deletes file."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.delete(f"/2.0/files/{file_id}")

    assert response.status_code == 204


def test_download_file(client: FlaskClient):
    """Test that GET /2.0/files/<id>/content downloads file content."""
    upload_response = _upload_file(client, content=b"hello world")
    file_id = upload_response.json["entries"][0]["id"]

    response = client.get(f"/2.0/files/{file_id}/content")

    assert response.status_code == 200
    assert response.data == b"hello world"


def test_upload_file_version(client: FlaskClient):
    """Test that POST /2.0/files/<id>/content uploads new version."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.post(
        f"/2.0/files/{file_id}/content",
        data={"file": (io.BytesIO(b"new content"), "test.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    data = response.json
    assert data["entries"][0]["file_version"]["version_number"] == 2


def test_copy_file(client: FlaskClient):
    """Test that POST /2.0/files/<id>/copy copies file."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.post(
        f"/2.0/files/{file_id}/copy",
        json={"name": "copy.txt", "parent": {"id": "0"}},
    )

    assert response.status_code == 201
    assert response.json["name"] == "copy.txt"


def test_preflight_check(client: FlaskClient):
    """Test that POST /2.0/files/upload_sessions returns upload token."""
    response = client.post(
        "/2.0/files/upload_sessions",
        json={"name": "unique_file.txt", "parent": {"id": "0"}},
    )

    assert response.status_code == 200
    assert "upload_token" in response.json

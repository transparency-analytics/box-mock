"""Tests for file routes."""

import hashlib
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


def test_upload_file_parent_not_found(client: FlaskClient):
    """POST /2.0/files/content returns 404 for a missing parent folder."""
    response = _upload_file(client, parent_id="does-not-exist")

    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_upload_file_without_content(client: FlaskClient):
    """POST /2.0/files/content returns 400 when no file part is provided."""
    response = client.post(
        "/2.0/files/content",
        data={
            "attributes": json.dumps({"name": "empty.txt", "parent": {"id": "0"}}),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.json["code"] == "bad_request"


def test_upload_file_returns_rclone_metadata(client: FlaskClient):
    """Uploaded file metadata includes fields rclone's Box backend reads."""
    content = b"test content"
    response = _upload_file(client, content=content)

    assert response.status_code == 201
    data = response.json["entries"][0]
    assert data["sequence_id"] == "1"
    assert data["version_number"] == "1"
    assert data["etag"]
    assert data["sha1"] == hashlib.sha1(content).hexdigest()
    assert data["modified_at"]
    assert data["content_created_at"]
    assert data["content_modified_at"]
    assert data["item_status"] == "active"
    assert data["owned_by"]["login"] == "service@boxmock.local"


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


def test_download_file_with_access_token_query_param(client: FlaskClient):
    """Identity in the access_token query param works without an auth header.

    This is how download links on /_browse carry the identity, since a
    browser click sends no Authorization header.
    """
    content = b"hello from the browser"
    upload_response = client.post(
        "/2.0/files/content",
        data={
            "attributes": json.dumps({"name": "hello.txt", "parent": {"id": "0"}}),
            "file": (io.BytesIO(content), "hello.txt"),
        },
        content_type="multipart/form-data",
        headers={"Authorization": "Identity=browse-ident"},
    )
    file_id = upload_response.json["entries"][0]["id"]

    response = client.get(
        f"/2.0/files/{file_id}/content?access_token=Identity%3Dbrowse-ident",
    )

    assert response.status_code == 200
    assert response.data == content
    assert "attachment" in response.headers["Content-Disposition"]


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
    assert data["entries"][0]["version_number"] == "2"
    assert data["entries"][0]["file_version"]["type"] == "file_version"
    assert data["entries"][0]["sha1"] == hashlib.sha1(b"new content").hexdigest()


def test_upload_file_version_not_found(client: FlaskClient):
    """POST /2.0/files/<id>/content returns 404 for a missing file."""
    response = client.post(
        "/2.0/files/does-not-exist/content",
        data={"file": (io.BytesIO(b"new content"), "test.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_upload_file_version_without_content(client: FlaskClient):
    """POST /2.0/files/<id>/content returns 400 when no file part is provided."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.post(
        f"/2.0/files/{file_id}/content",
        data={},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.json["code"] == "bad_request"


def test_list_file_versions_single(client: FlaskClient):
    """GET /2.0/files/<id>/versions excludes the current version after upload."""
    upload_response = _upload_file(client, content=b"hello")
    file_id = upload_response.json["entries"][0]["id"]

    response = client.get(f"/2.0/files/{file_id}/versions")

    assert response.status_code == 200
    data = response.json
    assert data["total_count"] == 0
    assert data["entries"] == []


def test_list_file_versions_after_replace(client: FlaskClient):
    """GET /2.0/files/<id>/versions returns only past versions after replace."""
    upload_response = _upload_file(client, content=b"version one")
    file_id = upload_response.json["entries"][0]["id"]

    client.post(
        f"/2.0/files/{file_id}/content",
        data={"file": (io.BytesIO(b"version two"), "test.txt")},
        content_type="multipart/form-data",
    )

    response = client.get(f"/2.0/files/{file_id}/versions")

    assert response.status_code == 200
    data = response.json
    assert data["total_count"] == 1
    assert len(data["entries"]) == 1
    assert data["entries"][0]["version_number"] == "1"
    assert data["entries"][0]["sha1"] == hashlib.sha1(b"version one").hexdigest()


def test_list_file_versions_excludes_current(client: FlaskClient):
    """GET /2.0/files/<id>/versions excludes the most recent version."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    for i in range(2, 4):
        client.post(
            f"/2.0/files/{file_id}/content",
            data={"file": (io.BytesIO(f"version {i}".encode()), "test.txt")},
            content_type="multipart/form-data",
        )

    response = client.get(f"/2.0/files/{file_id}/versions")

    assert response.status_code == 200
    data = response.json
    assert data["total_count"] == 2
    assert len(data["entries"]) == 2
    assert [entry["version_number"] for entry in data["entries"]] == ["1", "2"]


def test_list_file_versions_not_found(client: FlaskClient):
    """GET /2.0/files/<id>/versions returns 404 for a missing file."""
    response = client.get("/2.0/files/does-not-exist/versions")

    assert response.status_code == 404
    assert response.json["code"] == "not_found"


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


def test_copy_file_not_found(client: FlaskClient):
    """POST /2.0/files/<id>/copy returns 404 for a missing source file."""
    response = client.post(
        "/2.0/files/does-not-exist/copy",
        json={"name": "copy.txt", "parent": {"id": "0"}},
    )

    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_copy_file_destination_folder_not_found(client: FlaskClient):
    """POST /2.0/files/<id>/copy returns 404 for a missing destination."""
    upload_response = _upload_file(client)
    file_id = upload_response.json["entries"][0]["id"]

    response = client.post(
        f"/2.0/files/{file_id}/copy",
        json={"name": "copy.txt", "parent": {"id": "does-not-exist"}},
    )

    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_preflight_check(client: FlaskClient):
    """Test that POST /2.0/files/upload_sessions returns upload token."""
    response = client.post(
        "/2.0/files/upload_sessions",
        json={"name": "unique_file.txt", "parent": {"id": "0"}},
    )

    assert response.status_code == 200
    assert "upload_token" in response.json


def test_rclone_pre_upload_check(client: FlaskClient):
    """OPTIONS /2.0/files/content/ returns the simple upload target."""
    response = client.open(
        "/2.0/files/content/",
        method="OPTIONS",
        json={"name": "unique_file.txt", "parent": {"id": "0"}, "size": 12},
    )

    assert response.status_code == 200
    assert response.json["upload_token"] == "dummy"
    assert response.json["upload_url"].endswith("/2.0/files/content")


def test_rclone_pre_upload_check_conflict(client: FlaskClient):
    """Existing file conflicts use rclone's expected single-object shape."""
    uploaded = _upload_file(client, name="exists.txt").json["entries"][0]

    response = client.open(
        "/2.0/files/content/",
        method="OPTIONS",
        json={"name": "exists.txt", "parent": {"id": "0"}, "size": 12},
    )

    assert response.status_code == 409
    data = response.json
    assert data["code"] == "item_name_in_use"
    conflict = data["context_info"]["conflicts"]
    assert isinstance(conflict, dict)
    assert conflict["type"] == "file"
    assert conflict["id"] == uploaded["id"]
    assert conflict["name"] == "exists.txt"


def test_rclone_pre_upload_check_parent_not_found(client: FlaskClient):
    """OPTIONS /2.0/files/content/ returns 404 for a missing parent folder."""
    response = client.open(
        "/2.0/files/content/",
        method="OPTIONS",
        json={"name": "orphan.txt", "parent": {"id": "does-not-exist"}},
    )

    assert response.status_code == 404
    assert response.json["code"] == "not_found"

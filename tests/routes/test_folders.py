"""Tests for folder routes."""

from flask.testing import FlaskClient


def test_create_folder(client: FlaskClient):
    """Test that POST /2.0/folders creates a folder."""
    response = client.post(
        "/2.0/folders",
        json={"name": "Test Folder", "parent": {"id": "0"}},
    )

    assert response.status_code == 201
    data = response.json
    assert data["type"] == "folder"
    assert data["name"] == "Test Folder"
    assert data["parent"]["id"] == "0"


def test_get_folder(client: FlaskClient):
    """Test that GET /2.0/folders/<id> returns folder."""
    response = client.get("/2.0/folders/0")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "folder"
    assert data["id"] == "0"


def test_update_folder(client: FlaskClient):
    """Test that PUT /2.0/folders/<id> updates folder."""
    create_response = client.post(
        "/2.0/folders",
        json={"name": "Original Name", "parent": {"id": "0"}},
    )
    folder_id = create_response.json["id"]

    response = client.put(
        f"/2.0/folders/{folder_id}",
        json={"name": "Updated Name"},
    )

    assert response.status_code == 200
    assert response.json["name"] == "Updated Name"


def test_delete_folder(client: FlaskClient):
    """Test that DELETE /2.0/folders/<id> deletes folder."""
    create_response = client.post(
        "/2.0/folders",
        json={"name": "To Delete", "parent": {"id": "0"}},
    )
    folder_id = create_response.json["id"]

    response = client.delete(f"/2.0/folders/{folder_id}")

    assert response.status_code == 204


def test_get_folder_items(client: FlaskClient):
    """Test that GET /2.0/folders/<id>/items returns folder contents."""
    response = client.get("/2.0/folders/0/items")

    assert response.status_code == 200
    data = response.json
    assert "entries" in data
    assert "total_count" in data

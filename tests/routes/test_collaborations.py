"""Tests for collaboration routes."""

from flask.testing import FlaskClient


def test_create_collaboration(client: FlaskClient):
    """Test that POST /2.0/collaborations creates a collaboration."""
    response = client.post(
        "/2.0/collaborations",
        json={
            "item": {"type": "folder", "id": "123"},
            "accessible_by": {"type": "user", "id": "456"},
            "role": "editor",
            "can_view_path": True,
        },
    )

    assert response.status_code == 201
    data = response.json
    assert data["type"] == "collaboration"
    assert data["item"] == {"type": "folder", "id": "123"}
    assert data["accessible_by"] == {"type": "user", "id": "456"}
    assert data["role"] == "editor"
    assert data["can_view_path"] is True


def test_get_collaboration(client: FlaskClient):
    """Test that GET /2.0/collaborations/<id> returns collaboration."""
    response = client.get("/2.0/collaborations/test-collab-id")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "collaboration"
    assert data["id"] == "test-collab-id"


def test_delete_collaboration(client: FlaskClient):
    """Test that DELETE /2.0/collaborations/<id> returns 204."""
    response = client.delete("/2.0/collaborations/test-collab-id")

    assert response.status_code == 204

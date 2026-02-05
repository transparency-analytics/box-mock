"""Tests for user routes."""

from flask.testing import FlaskClient


def test_get_current_user(client: FlaskClient):
    """Test that GET /2.0/users/me returns current user."""
    response = client.get("/2.0/users/me")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "user"
    assert "id" in data


def test_list_users(client: FlaskClient):
    """Test that GET /2.0/users returns user list."""
    response = client.get("/2.0/users")

    assert response.status_code == 200
    data = response.json
    assert "entries" in data
    assert "total_count" in data


def test_create_user(client: FlaskClient):
    """Test that POST /2.0/users creates a user."""
    response = client.post(
        "/2.0/users",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "login": "test@example.com",
        },
    )

    assert response.status_code == 201
    data = response.json
    assert data["type"] == "user"
    assert data["name"] == "Test User"
    assert data["email"] == "test@example.com"


def test_get_user(client: FlaskClient):
    """Test that GET /2.0/users/<id> returns user."""
    create_response = client.post(
        "/2.0/users",
        json={"name": "Lookup User", "email": "lookup@example.com"},
    )
    user_id = create_response.json["id"]

    response = client.get(f"/2.0/users/{user_id}")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "user"
    assert data["id"] == user_id


def test_delete_user(client: FlaskClient):
    """Test that DELETE /2.0/users/<id> deletes user."""
    create_response = client.post(
        "/2.0/users",
        json={"name": "To Delete", "email": "delete@example.com"},
    )
    user_id = create_response.json["id"]

    response = client.delete(f"/2.0/users/{user_id}")

    assert response.status_code == 204

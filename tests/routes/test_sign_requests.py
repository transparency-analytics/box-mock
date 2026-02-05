"""Tests for sign request routes."""

from flask.testing import FlaskClient


def test_create_sign_request(client: FlaskClient):
    """Test that POST /2.0/sign_requests creates a sign request."""
    response = client.post(
        "/2.0/sign_requests",
        json={
            "source_files": [{"id": "file-123"}],
            "signers": [{"email": "signer@example.com", "role": "signer"}],
            "parent_folder": {"id": "0"},
            "redirect_url": "https://example.com/callback",
        },
    )

    assert response.status_code == 201
    data = response.json
    assert data["type"] == "sign-request"
    assert data["status"] == "created"
    assert len(data["signers"]) == 1
    assert data["signers"][0]["email"] == "signer@example.com"


def test_get_sign_request(client: FlaskClient):
    """Test that GET /2.0/sign_requests/<id> returns sign request."""
    create_response = client.post(
        "/2.0/sign_requests",
        json={
            "source_files": [{"id": "file-123"}],
            "signers": [{"email": "signer@example.com"}],
            "parent_folder": {"id": "0"},
        },
    )
    sign_request_id = create_response.json["id"]

    response = client.get(f"/2.0/sign_requests/{sign_request_id}")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "sign-request"
    assert data["id"] == sign_request_id

"""Tests for sign request routes."""

from urllib.parse import urlparse

from flask.testing import FlaskClient

DEFAULT_SIGNERS = [{"email": "signer@example.com", "role": "signer"}]


def _create(client: FlaskClient, signers: list = DEFAULT_SIGNERS) -> dict:
    """Create a sign request and return the parsed response body."""
    response = client.post(
        "/2.0/sign_requests",
        json={
            "source_files": [{"id": "file-123"}],
            "signers": signers,
            "parent_folder": {"id": "0"},
            "redirect_url": "https://example.com/callback",
        },
    )
    assert response.status_code == 201
    return response.json


def _embed_path(embed_url: str) -> str:
    """Reduce a full embed URL to a path+query that the test client can hit."""
    parsed = urlparse(embed_url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def test_create_sign_request(client: FlaskClient):
    """POST /2.0/sign_requests creates a sign request."""
    data = _create(client)
    assert data["type"] == "sign-request"
    assert data["status"] == "created"
    assert len(data["signers"]) == 1
    assert data["signers"][0]["email"] == "signer@example.com"
    assert data["signers"][0]["embed_url"].startswith("http")
    assert "Identity=" in data["signers"][0]["embed_url"]


def test_get_sign_request(client: FlaskClient):
    """GET /2.0/sign_requests/<id> returns sign request."""
    created = _create(client)
    response = client.get(f"/2.0/sign_requests/{created['id']}")

    assert response.status_code == 200
    data = response.json
    assert data["type"] == "sign-request"
    assert data["id"] == created["id"]


def test_create_sign_request_creates_document(client: FlaskClient):
    """Create produces a real File whose content starts as 'unsigned'."""
    data = _create(client)
    files = data["sign_files"]["files"]
    assert len(files) == 1
    file_id = files[0]["id"]

    content_response = client.get(f"/2.0/files/{file_id}/content")
    assert content_response.status_code == 200
    assert content_response.data == b"unsigned"

    meta_response = client.get(f"/2.0/files/{file_id}")
    assert meta_response.status_code == 200
    assert meta_response.json["parent"]["id"] == "0"


def test_embed_url_renders_form(client: FlaskClient):
    """GET on the embed URL returns an HTML page with a checkbox."""
    data = _create(client)
    embed_url = data["signers"][0]["embed_url"]

    response = client.get(_embed_path(embed_url))
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'type="checkbox"' in body
    assert "signer@example.com" in body


def test_submit_embed_signs_document_for_one_signer(client: FlaskClient):
    """Partial signing: status stays 'created' until every signer submits."""
    data = _create(
        client,
        signers=[
            {"email": "a@example.com"},
            {"email": "b@example.com"},
        ],
    )
    sign_request_id = data["id"]
    file_id = data["sign_files"]["files"][0]["id"]
    signer_a = next(s for s in data["signers"] if s["email"] == "a@example.com")

    submit = client.post(_embed_path(signer_a["embed_url"]), data={"signed": "1"})
    assert submit.status_code == 200

    content = client.get(f"/2.0/files/{file_id}/content").data
    assert content == b"unsigned\nsigned by a@example.com"

    refreshed = client.get(f"/2.0/sign_requests/{sign_request_id}").json
    assert refreshed["status"] == "created"
    assert refreshed["finished_at"] is None
    a_state = next(s for s in refreshed["signers"] if s["email"] == "a@example.com")
    b_state = next(s for s in refreshed["signers"] if s["email"] == "b@example.com")
    assert a_state["signer_decision"]["type"] == "signed"
    assert b_state["signer_decision"] is None


def test_submit_embed_signs_request_when_all_signers_done(client: FlaskClient):
    """All signers submitting flips status to 'signed' and stamps finished_at."""
    data = _create(
        client,
        signers=[
            {"email": "a@example.com"},
            {"email": "b@example.com"},
        ],
    )
    sign_request_id = data["id"]
    file_id = data["sign_files"]["files"][0]["id"]

    for signer in data["signers"]:
        resp = client.post(_embed_path(signer["embed_url"]), data={"signed": "1"})
        assert resp.status_code in (200, 302)

    refreshed = client.get(f"/2.0/sign_requests/{sign_request_id}").json
    assert refreshed["status"] == "signed"
    assert refreshed["finished_at"] is not None

    content = client.get(f"/2.0/files/{file_id}/content").data
    assert content == b"unsigned\nsigned by a@example.com\nsigned by b@example.com"


def test_submit_embed_requires_checkbox(client: FlaskClient):
    """Submitting without the checkbox re-renders the form and does not mutate."""
    data = _create(client)
    file_id = data["sign_files"]["files"][0]["id"]
    embed_path = _embed_path(data["signers"][0]["embed_url"])

    response = client.post(embed_path, data={})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'type="checkbox"' in body
    assert "must check" in body.lower()

    content = client.get(f"/2.0/files/{file_id}/content").data
    assert content == b"unsigned"

    sr = client.get(f"/2.0/sign_requests/{data['id']}").json
    assert sr["status"] == "created"
    assert sr["signers"][0]["signer_decision"] is None

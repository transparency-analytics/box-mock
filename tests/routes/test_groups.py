"""Tests for group and group membership routes."""

from flask.testing import FlaskClient


def _create_user(client: FlaskClient, name: str, email: str) -> dict:
    response = client.post(
        "/2.0/users",
        json={"name": name, "email": email, "login": email},
    )
    assert response.status_code == 201
    return response.json


def _create_group(client: FlaskClient, name: str) -> dict:
    response = client.post("/2.0/groups", json={"name": name})
    assert response.status_code == 201
    return response.json


def test_create_group(client: FlaskClient):
    """Test that POST /2.0/groups creates a group."""
    response = client.post("/2.0/groups", json={"name": "TPA Internal"})

    assert response.status_code == 201
    data = response.json
    assert data["type"] == "group"
    assert data["name"] == "TPA Internal"
    assert data["group_type"] == "managed_group"


def test_create_group_duplicate_name_returns_409(client: FlaskClient):
    """Test duplicate group names return 409 conflict."""
    first = client.post("/2.0/groups", json={"name": "Analyst Managers"})
    second = client.post("/2.0/groups", json={"name": "Analyst Managers"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json["code"] == "conflict"


def test_list_groups_filter_term(client: FlaskClient):
    """Test list groups supports filter_term."""
    _create_group(client, "TPA Internal")
    _create_group(client, "Sales Rep Managers")

    response = client.get("/2.0/groups?filter_term=Sales")

    assert response.status_code == 200
    data = response.json
    assert data["total_count"] == 1
    assert data["entries"][0]["name"] == "Sales Rep Managers"


def test_get_group_by_id(client: FlaskClient):
    """Test get group by ID returns group data."""
    created = _create_group(client, "Compliance Group")

    response = client.get(f"/2.0/groups/{created['id']}")

    assert response.status_code == 200
    assert response.json["id"] == created["id"]
    assert response.json["name"] == "Compliance Group"


def test_get_group_by_id_not_found(client: FlaskClient):
    """Test missing group returns 404."""
    response = client.get("/2.0/groups/missing-group-id")

    assert response.status_code == 404
    assert response.json["code"] == "not_found"


def test_delete_group_cascades_memberships(client: FlaskClient):
    """Test deleting group also removes memberships."""
    user = _create_user(client, "Member User", "member@example.com")
    group = _create_group(client, "Delete Me Group")
    membership_response = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user["id"]}, "group": {"id": group["id"]}},
    )
    membership_id = membership_response.json["id"]
    assert membership_response.status_code == 201

    delete_response = client.delete(f"/2.0/groups/{group['id']}")
    get_membership_response = client.get(f"/2.0/group_memberships/{membership_id}")

    assert delete_response.status_code == 204
    assert get_membership_response.status_code == 404


def test_create_group_membership(client: FlaskClient):
    """Test creating a group membership succeeds."""
    user = _create_user(client, "Analyst User", "analyst@example.com")
    group = _create_group(client, "Analyst Managers")

    response = client.post(
        "/2.0/group_memberships",
        json={
            "user": {"id": user["id"]},
            "group": {"id": group["id"]},
            "role": "member",
        },
    )

    assert response.status_code == 201
    data = response.json
    assert data["type"] == "group_membership"
    assert data["user"]["id"] == user["id"]
    assert data["group"]["id"] == group["id"]
    assert data["role"] == "member"


def test_create_membership_duplicate_returns_409(client: FlaskClient):
    """Test duplicate user/group memberships return 409 conflict."""
    user = _create_user(client, "Dup User", "dup@example.com")
    group = _create_group(client, "TPA Internal")

    first = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user["id"]}, "group": {"id": group["id"]}},
    )
    second = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user["id"]}, "group": {"id": group["id"]}},
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json["code"] == "conflict"
    assert "already exists in group" in second.json["message"]


def test_create_membership_missing_user_or_group_404(client: FlaskClient):
    """Test missing user/group references return 404."""
    group = _create_group(client, "Sales Rep Managers")

    missing_user = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": "no-user"}, "group": {"id": group["id"]}},
    )
    assert missing_user.status_code == 404
    assert missing_user.json["message"] == "User not found"

    user = _create_user(client, "Missing Group User", "nogroup@example.com")
    missing_group = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user["id"]}, "group": {"id": "no-group"}},
    )
    assert missing_group.status_code == 404
    assert missing_group.json["message"] == "Group not found"


def test_get_group_memberships_paged(client: FlaskClient):
    """Test list group memberships supports pagination."""
    group = _create_group(client, "Paged Group")
    user1 = _create_user(client, "User One", "user1@example.com")
    user2 = _create_user(client, "User Two", "user2@example.com")

    client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user1["id"]}, "group": {"id": group["id"]}},
    )
    client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user2["id"]}, "group": {"id": group["id"]}},
    )

    response = client.get(f"/2.0/groups/{group['id']}/memberships?limit=1&offset=1")

    assert response.status_code == 200
    data = response.json
    assert data["total_count"] == 2
    assert data["limit"] == 1
    assert data["offset"] == 1
    assert len(data["entries"]) == 1


def test_get_group_membership_by_id(client: FlaskClient):
    """Test get group membership by ID returns membership."""
    user = _create_user(client, "Membership User", "membership@example.com")
    group = _create_group(client, "Membership Group")
    created = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user["id"]}, "group": {"id": group["id"]}},
    ).json

    response = client.get(f"/2.0/group_memberships/{created['id']}")

    assert response.status_code == 200
    assert response.json["id"] == created["id"]


def test_delete_group_membership(client: FlaskClient):
    """Test deleting group membership returns 204 and removes record."""
    user = _create_user(client, "Delete Membership User", "delmembership@example.com")
    group = _create_group(client, "Delete Membership Group")
    created = client.post(
        "/2.0/group_memberships",
        json={"user": {"id": user["id"]}, "group": {"id": group["id"]}},
    ).json

    delete_response = client.delete(f"/2.0/group_memberships/{created['id']}")
    get_response = client.get(f"/2.0/group_memberships/{created['id']}")

    assert delete_response.status_code == 204
    assert get_response.status_code == 404

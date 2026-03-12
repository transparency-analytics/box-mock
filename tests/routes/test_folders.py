"""Tests for folder routes."""

import io
import json

from flask.testing import FlaskClient


def _upload_file(
    client: FlaskClient,
    name: str = "test.txt",
    content: bytes = b"hello",
    parent_id: str = "0",
) -> dict:
    resp = client.post(
        "/2.0/files/content",
        data={
            "attributes": json.dumps({"name": name, "parent": {"id": parent_id}}),
            "file": (io.BytesIO(content), name),
        },
        content_type="multipart/form-data",
    )
    return resp.json["entries"][0]


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


def test_get_folder_not_found(client: FlaskClient):
    """Test that GET /2.0/folders/<id> returns 404 for missing folder."""
    response = client.get("/2.0/folders/does-not-exist")
    assert response.status_code == 404


def test_get_folder_has_required_fields_for_picker(client: FlaskClient):
    """GET /2.0/folders/<id> must return item_collection,
    path_collection, and permissions so that the Box UI Elements
    picker does not throw 'Bad box item!'.
    """
    response = client.get("/2.0/folders/0")

    assert response.status_code == 200
    data = response.json

    # item_collection with all required numeric fields
    assert "item_collection" in data
    ic = data["item_collection"]
    assert isinstance(ic["entries"], list)
    assert isinstance(ic["total_count"], int)
    assert isinstance(ic["limit"], int)
    assert isinstance(ic["offset"], int)

    # path_collection with entries list
    assert "path_collection" in data
    pc = data["path_collection"]
    assert isinstance(pc["entries"], list)
    assert isinstance(pc["total_count"], int)

    # permissions block
    assert "permissions" in data
    perms = data["permissions"]
    for key in ("can_download", "can_upload", "can_rename", "can_delete", "can_share"):
        assert key in perms, f"permissions.{key} is missing"


def test_get_folder_item_collection_contains_children(client: FlaskClient):
    """item_collection.entries should include sub-folders and files."""
    # Create a sub-folder inside root
    sub = client.post(
        "/2.0/folders",
        json={"name": "Sub", "parent": {"id": "0"}},
    ).json
    sub_id = sub["id"]

    # Upload a file into root
    _upload_file(client, name="readme.txt", parent_id="0")

    response = client.get("/2.0/folders/0")
    entries = response.json["item_collection"]["entries"]
    ids = {e["id"] for e in entries}

    assert sub_id in ids
    assert any(e["type"] == "file" and e["name"] == "readme.txt" for e in entries)


def test_get_folder_item_collection_honours_limit_and_offset(client: FlaskClient):
    """limit and offset query params control paging of item_collection.entries."""
    for i in range(5):
        client.post(
            "/2.0/folders",
            json={"name": f"Child {i}", "parent": {"id": "0"}},
        )

    full = client.get("/2.0/folders/0").json["item_collection"]
    total = full["total_count"]
    assert total >= 5

    page = client.get("/2.0/folders/0?limit=2&offset=0").json["item_collection"]
    assert page["limit"] == 2
    assert page["offset"] == 0
    assert len(page["entries"]) == 2

    page2 = client.get("/2.0/folders/0?limit=2&offset=2").json["item_collection"]
    assert page2["offset"] == 2
    # entries on page 2 should be different from page 1
    ids1 = {e["id"] for e in page["entries"]}
    ids2 = {e["id"] for e in page2["entries"]}
    assert ids1.isdisjoint(ids2)


def test_get_folder_item_collection_sorted_by_name_asc(client: FlaskClient):
    """sort=name&direction=asc returns entries in ascending name order."""
    for name in ["Zebra", "Apple", "Mango"]:
        client.post(
            "/2.0/folders",
            json={"name": name, "parent": {"id": "0"}},
        )

    entries = client.get("/2.0/folders/0?sort=name&direction=asc").json[
        "item_collection"
    ]["entries"]
    names = [e["name"] for e in entries]
    assert names == sorted(names, key=str.lower)


def test_get_folder_item_collection_sorted_by_name_desc(client: FlaskClient):
    """sort=name&direction=desc returns entries in descending name order."""
    for name in ["Zebra", "Apple", "Mango"]:
        client.post(
            "/2.0/folders",
            json={"name": name, "parent": {"id": "0"}},
        )

    entries = client.get("/2.0/folders/0?sort=name&direction=desc").json[
        "item_collection"
    ]["entries"]
    names = [e["name"] for e in entries]
    assert names == sorted(names, key=str.lower, reverse=True)


def test_get_folder_path_collection_shows_ancestors(client: FlaskClient):
    """path_collection.entries contains the ancestor chain from root to parent."""
    parent = client.post(
        "/2.0/folders",
        json={"name": "Parent", "parent": {"id": "0"}},
    ).json
    child = client.post(
        "/2.0/folders",
        json={"name": "Child", "parent": {"id": parent["id"]}},
    ).json

    data = client.get(f"/2.0/folders/{child['id']}").json
    path_ids = [e["id"] for e in data["path_collection"]["entries"]]

    # path should include root ("0") and the parent
    assert "0" in path_ids
    assert parent["id"] in path_ids
    # child itself should NOT appear in path_collection
    assert child["id"] not in path_ids


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

"""Folder routes for Box Mock API."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from box_mock.db import db
from box_mock.models import Folder

folders_bp = Blueprint("folders", __name__, url_prefix="/2.0")


@folders_bp.route("/folders", methods=["POST"])
def create_folder() -> tuple[Response, int]:
    """Create a new folder."""
    data = request.get_json()
    name = data.get("name")
    parent_data = data.get("parent", {})
    parent_id = parent_data.get("id", "0")

    parent = db.session.get(Folder, parent_id)
    if not parent:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Parent folder not found",
            },
        ), 404

    folder = Folder(name=name, parent_id=parent_id)
    db.session.add(folder)
    db.session.commit()
    return jsonify(folder.to_dict()), 201


@folders_bp.route("/folders/<folder_id>", methods=["GET"])
def get_folder(folder_id: str) -> Response | tuple[Response, int]:
    """Get folder by ID."""
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Folder not found"},
        ), 404
    return jsonify(folder.to_dict())


@folders_bp.route("/folders/<folder_id>", methods=["PUT"])
def update_folder(folder_id: str) -> Response | tuple[Response, int]:
    """Update folder (name or parent)."""
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Folder not found"},
        ), 404

    data = request.get_json()
    if "name" in data:
        folder.name = data["name"]
    if "parent" in data:
        folder.parent_id = data["parent"].get("id")

    db.session.commit()
    return jsonify(folder.to_dict())


@folders_bp.route("/folders/<folder_id>", methods=["DELETE"])
def delete_folder(folder_id: str) -> tuple[Response, int] | tuple[str, int]:
    """Delete folder by ID (recursive)."""
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Folder not found"},
        ), 404
    if folder_id == "0":
        return jsonify(
            {
                "type": "error",
                "code": "forbidden",
                "message": "Cannot delete root folder",
            },
        ), 403

    db.session.delete(folder)
    db.session.commit()
    return "", 204


@folders_bp.route("/folders/<folder_id>/items", methods=["GET"])
def get_folder_items(folder_id: str) -> Response | tuple[Response, int]:
    """List items in a folder (subfolders and files)."""
    folder = db.session.get(Folder, folder_id)
    if not folder:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Folder not found"},
        ), 404

    items = [child.to_dict() for child in folder.children]
    items.extend(file.to_dict() for file in folder.files)

    return jsonify({"entries": items, "total_count": len(items)})

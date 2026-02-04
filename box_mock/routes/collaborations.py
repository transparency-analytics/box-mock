"""Collaboration routes for Box Mock API."""

from __future__ import annotations

import uuid

from flask import Blueprint, Response, jsonify, request

collaborations_bp = Blueprint("collaborations", __name__, url_prefix="/2.0")


@collaborations_bp.route("/collaborations", methods=["POST"])
def create_collaboration() -> tuple[Response, int]:
    """Create a collaboration (no-op, returns fake success)."""
    data = request.get_json()
    item = data.get("item", {})
    accessible_by = data.get("accessible_by", {})
    role = data.get("role", "editor")
    can_view_path = data.get("can_view_path", False)

    return jsonify(
        {
            "type": "collaboration",
            "id": str(uuid.uuid4()),
            "item": item,
            "accessible_by": accessible_by,
            "role": role,
            "can_view_path": can_view_path,
        },
    ), 201


@collaborations_bp.route("/collaborations/<collab_id>", methods=["GET"])
def get_collaboration(collab_id: str) -> Response:
    """Get collaboration by ID (no-op)."""
    return jsonify(
        {
            "type": "collaboration",
            "id": collab_id,
            "item": {"type": "folder", "id": "0"},
            "accessible_by": {"type": "user", "id": "unknown"},
            "role": "editor",
        },
    )


@collaborations_bp.route("/collaborations/<collab_id>", methods=["DELETE"])
def delete_collaboration(collab_id: str) -> tuple[str, int]:  # noqa: ARG001
    """Delete collaboration (no-op)."""
    return "", 204

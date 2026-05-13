"""Group and group membership routes for Box Mock API."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

from box_mock.db import db
from box_mock.models import Group, GroupMembership, User

groups_bp = Blueprint("groups", __name__, url_prefix="/2.0")
memberships_bp = Blueprint("memberships", __name__, url_prefix="/2.0")


def _parse_paging() -> tuple[int, int]:
    """Parse limit/offset query parameters with safe defaults."""
    try:
        limit = int(request.args.get("limit", 100))
    except (ValueError, TypeError):
        limit = 100
    try:
        offset = int(request.args.get("offset", 0))
    except (ValueError, TypeError):
        offset = 0
    return limit, offset


@groups_bp.route("/groups", methods=["POST"])
def create_group() -> tuple[Response, int]:
    """Create a new group."""
    data = request.get_json() or {}
    name = data.get("name")
    if not name:
        return jsonify(
            {
                "type": "error",
                "status": 400,
                "code": "bad_request",
                "message": "name is required",
            },
        ), 400

    existing = db.session.query(Group).filter(Group.name == name).first()
    if existing:
        return jsonify(
            {
                "type": "error",
                "status": 409,
                "code": "conflict",
                "message": "Group with this name already exists",
            },
        ), 409

    group = Group(
        name=name,
        description=data.get("description"),
        provenance=data.get("provenance"),
        external_sync_identifier=data.get("external_sync_identifier"),
        invitability_level=data.get("invitability_level"),
        member_viewability_level=data.get("member_viewability_level"),
    )
    db.session.add(group)
    db.session.commit()
    return jsonify(group.to_dict()), 201


@groups_bp.route("/groups", methods=["GET"])
def list_groups() -> Response:
    """List groups, optionally filtered by name."""
    filter_term = request.args.get("filter_term", "")
    query = db.session.query(Group)
    if filter_term:
        query = query.filter(Group.name.ilike(f"%{filter_term}%"))

    groups = query.order_by(Group.name.asc()).all()
    limit, offset = _parse_paging()
    page = groups[offset : offset + limit]
    return jsonify(
        {
            "entries": [group.to_dict() for group in page],
            "total_count": len(groups),
            "limit": limit,
            "offset": offset,
        },
    )


@groups_bp.route("/groups/<group_id>", methods=["GET"])
def get_group(group_id: str) -> Response | tuple[Response, int]:
    """Get group by ID."""
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Group not found"},
        ), 404
    return jsonify(group.to_dict())


@groups_bp.route("/groups/<group_id>", methods=["DELETE"])
def delete_group(group_id: str) -> tuple[Response, int] | tuple[str, int]:
    """Delete group by ID."""
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Group not found"},
        ), 404

    db.session.delete(group)
    db.session.commit()
    return "", 204


@groups_bp.route("/groups/<group_id>/memberships", methods=["GET"])
def get_group_memberships(group_id: str) -> Response | tuple[Response, int]:
    """List memberships for a specific group."""
    group = db.session.get(Group, group_id)
    if not group:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Group not found"},
        ), 404

    memberships = (
        db.session.query(GroupMembership)
        .filter(GroupMembership.group_id == group_id)
        .order_by(GroupMembership.created_at.asc())
        .all()
    )
    limit, offset = _parse_paging()
    page = memberships[offset : offset + limit]
    return jsonify(
        {
            "entries": [membership.to_dict() for membership in page],
            "total_count": len(memberships),
            "limit": limit,
            "offset": offset,
        },
    )


@memberships_bp.route("/group_memberships", methods=["POST"])
def create_group_membership() -> tuple[Response, int]:
    """Create a new group membership."""
    data = request.get_json() or {}
    user_id = (data.get("user") or {}).get("id")
    group_id = (data.get("group") or {}).get("id")
    role = data.get("role", "member")

    if not user_id or not group_id:
        return jsonify(
            {
                "type": "error",
                "status": 400,
                "code": "bad_request",
                "message": "user.id and group.id are required",
            },
        ), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "User not found"},
        ), 404

    group = db.session.get(Group, group_id)
    if not group:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Group not found"},
        ), 404

    existing = (
        db.session.query(GroupMembership)
        .filter(
            GroupMembership.user_id == user_id,
            GroupMembership.group_id == group_id,
        )
        .first()
    )
    if existing:
        return jsonify(
            {
                "type": "error",
                "status": 409,
                "code": "conflict",
                "message": "User is already a member of this group",
            },
        ), 409

    membership = GroupMembership(user_id=user_id, group_id=group_id, role=role)
    db.session.add(membership)
    db.session.commit()
    return jsonify(membership.to_dict()), 201


@memberships_bp.route("/group_memberships/<membership_id>", methods=["GET"])
def get_group_membership(membership_id: str) -> Response | tuple[Response, int]:
    """Get membership by ID."""
    membership = db.session.get(GroupMembership, membership_id)
    if not membership:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Group membership not found",
            },
        ), 404
    return jsonify(membership.to_dict())


@memberships_bp.route("/group_memberships/<membership_id>", methods=["DELETE"])
def delete_group_membership(
    membership_id: str,
) -> tuple[Response, int] | tuple[str, int]:
    """Delete membership by ID."""
    membership = db.session.get(GroupMembership, membership_id)
    if not membership:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Group membership not found",
            },
        ), 404

    db.session.delete(membership)
    db.session.commit()
    return "", 204

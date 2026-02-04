"""User routes for Box Mock API."""

from __future__ import annotations

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import or_

from box_mock.db import db
from box_mock.models import User

users_bp = Blueprint("users", __name__, url_prefix="/2.0")


@users_bp.route("/users/me", methods=["GET"])
def get_current_user() -> Response:
    """Get current user info (returns first user or creates a service user)."""
    user = db.session.query(User).first()
    if not user:
        user = User(name="Box Mock Service", login="service@boxmock.local")
        db.session.add(user)
        db.session.commit()
    return jsonify(user.to_dict())


@users_bp.route("/users", methods=["GET"])
def list_users() -> Response:
    """List users, optionally filtered by filter_term."""
    filter_term = request.args.get("filter_term", "")
    query = db.session.query(User)
    if filter_term:
        query = query.filter(
            or_(
                User.name.ilike(f"%{filter_term}%"),
                User.email.ilike(f"%{filter_term}%"),
                User.login.ilike(f"%{filter_term}%"),
            ),
        )
    users = query.all()
    return jsonify({"entries": [u.to_dict() for u in users], "total_count": len(users)})


@users_bp.route("/users", methods=["POST"])
def create_user() -> tuple[Response, int]:
    """Create a new user."""
    data = request.get_json()
    user = User(
        name=data.get("name", "Unnamed User"),
        email=data.get("email"),
        login=data.get("login"),
        is_platform_access_only=data.get("is_platform_access_only", False),
        job_title=data.get("job_title"),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@users_bp.route("/users/<user_id>", methods=["GET"])
def get_user(user_id: str) -> Response | tuple[Response, int]:
    """Get user by ID."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "User not found"},
        ), 404
    return jsonify(user.to_dict())


@users_bp.route("/users/<user_id>", methods=["DELETE"])
def delete_user(user_id: str) -> tuple[Response, int] | tuple[str, int]:
    """Delete user by ID."""
    user = db.session.get(User, user_id)
    if not user:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "User not found"},
        ), 404
    db.session.delete(user)
    db.session.commit()
    return "", 204

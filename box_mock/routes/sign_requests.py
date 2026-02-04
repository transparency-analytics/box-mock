"""Sign request routes for Box Mock API."""

from __future__ import annotations

import json
import uuid

from flask import Blueprint, Response, jsonify, request

from box_mock.db import db
from box_mock.models import SignRequest

sign_requests_bp = Blueprint("sign_requests", __name__, url_prefix="/2.0")


@sign_requests_bp.route("/sign_requests", methods=["POST"])
def create_sign_request() -> tuple[Response, int]:
    """Create a Box Sign request."""
    data = request.get_json()

    source_files = data.get("source_files", [])
    signers_data = data.get("signers", [])
    parent_folder = data.get("parent_folder", {})
    redirect_url = data.get("redirect_url")

    sign_request_id = str(uuid.uuid4())

    signers = [
        {
            "type": "signer",
            "email": s.get("email"),
            "role": s.get("role", "signer"),
            "embed_url": f"https://box-mock.local/sign/{sign_request_id}/{uuid.uuid4()}",
        }
        for s in signers_data
    ]

    files = [
        {
            "type": "file",
            "id": str(uuid.uuid4()),
            "name": f"signed_document_{sf.get('id', uuid.uuid4())}.pdf",
        }
        for sf in source_files
    ]

    sign_request = SignRequest(
        id=sign_request_id,
        parent_folder_id=parent_folder.get("id"),
        redirect_url=redirect_url,
        status="created",
        signers_json=json.dumps(signers),
        files_json=json.dumps(files),
    )
    db.session.add(sign_request)
    db.session.commit()

    return jsonify(sign_request.to_dict()), 201


@sign_requests_bp.route("/sign_requests/<sign_request_id>", methods=["GET"])
def get_sign_request(sign_request_id: str) -> Response | tuple[Response, int]:
    """Get a sign request by ID."""
    sign_request = db.session.get(SignRequest, sign_request_id)
    if not sign_request:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Sign request not found",
            },
        ), 404

    return jsonify(sign_request.to_dict())

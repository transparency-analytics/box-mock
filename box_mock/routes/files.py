"""File routes for Box Mock API."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
import uuid
from typing import TYPE_CHECKING

from flask import Blueprint, Response, g, jsonify, request, send_file

from box_mock.db import db
from box_mock.models import File, FileVersion, Folder

files_bp = Blueprint("files", __name__, url_prefix="/2.0")

if TYPE_CHECKING:
    from pathlib import Path


def get_files_dir() -> Path:
    """
    Get the files directory for the current identity.

    When ``app.config["FILES_DIR"]`` is set (e.g. in tests) it is used as the
    root instead of the default ``DATA_DIR / identity / files`` path.
    """
    from flask import current_app  # noqa: PLC0415

    identity = g.get("identity", "default")
    files_root: Path | None = current_app.config.get("FILES_DIR")
    if files_root is not None:
        files_dir = files_root / identity
    else:
        from box_mock.db import DATA_DIR  # noqa: PLC0415

        files_dir = DATA_DIR / identity / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    return files_dir


def get_file_dir(file_id: str) -> Path:
    """Get filesystem directory for all versions of a file."""
    return get_files_dir() / file_id


def get_version_path(file_id: str, version_id: str) -> Path:
    """Get filesystem path for a specific file version."""
    return get_file_dir(file_id) / version_id


def get_file_path(file_id: str) -> Path:
    """Get filesystem path for a file's current version content."""
    file = db.session.get(File, file_id)
    if file is None or file.current_version is None:
        return get_file_dir(file_id)
    return get_version_path(file_id, file.current_version.id)


def create_version(
    file: File,
    content: bytes,
    *,
    name: str | None = None,
) -> FileVersion:
    """Create a new version for a file and write its content to disk."""
    version_number = (
        file.current_version.version_number if file.current_version else 0
    ) + 1
    version_name = name if name is not None else file.name
    version = FileVersion(
        file_id=file.id,
        version_number=version_number,
        name=version_name,
        size=len(content),
        sha1=hashlib.sha1(content).hexdigest(),
    )
    db.session.add(version)
    db.session.flush()

    version_path = get_version_path(file.id, version.id)
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_bytes(content)
    return version


@files_bp.route("/files/<file_id>", methods=["GET"])
def get_file(file_id: str) -> Response | tuple[Response, int]:
    """Get file metadata by ID."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404
    base_url = request.url_root.rstrip("/")
    content_url = f"{base_url}/2.0/files/{file_id}/content"
    data = file.to_dict()
    data["authenticated_download_url"] = content_url
    ext = (file.name.rsplit(".", 1)[-1].lower()) if "." in file.name else ""
    if ext == "pdf":
        rep_entries = [
            {
                "representation": "pdf",
                "status": {"state": "success"},
                "content": {"url_template": f"{content_url}{{+asset_path}}"},
                "properties": {},
            }
        ]
    else:
        rep_entries = []
    data["representations"] = {"entries": rep_entries}
    return jsonify(data)


@files_bp.route("/files/<file_id>", methods=["PUT"])
def update_file(file_id: str) -> Response | tuple[Response, int]:
    """Update file metadata (name)."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404

    data = request.get_json()
    if "name" in data:
        file.name = data["name"]

    db.session.commit()
    return jsonify(file.to_dict())


@files_bp.route("/files/<file_id>", methods=["DELETE"])
def delete_file(file_id: str) -> tuple[Response, int] | tuple[str, int]:
    """Delete file by ID."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404

    file_dir = get_file_dir(file_id)
    if file_dir.exists():
        shutil.rmtree(file_dir)

    db.session.delete(file)
    db.session.commit()
    return "", 204


@files_bp.route("/files/<file_id>/content", methods=["GET"])
def download_file(file_id: str) -> Response | tuple[Response, int]:
    """Download file content."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404

    version = file.current_version
    if version is None:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File content not found"},
        ), 404

    file_path = get_version_path(file_id, version.id)
    if not file_path.exists():
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File content not found"},
        ), 404

    mime_type, _ = mimetypes.guess_type(file.name)
    return send_file(
        file_path,
        download_name=file.name,
        mimetype=mime_type or "application/octet-stream",
        as_attachment=True,
    )


@files_bp.route("/files/<file_id>/versions", methods=["GET"])
def list_file_versions(file_id: str) -> Response | tuple[Response, int]:
    """List past versions for a file (excludes the current version)."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404

    past_versions = file.versions[:-1] if file.versions else []
    return jsonify(
        {
            "entries": [version.to_dict() for version in past_versions],
            "total_count": len(past_versions),
        },
    )


def extract_file_content() -> bytes | None:
    """Extract file content from request, handling various multipart formats."""
    for key in request.files:
        f = request.files[key]
        if f is not None:
            return f.read()
    return None


@files_bp.route("/files/content/", methods=["OPTIONS"])
def pre_upload_check() -> tuple[Response, int]:
    """Check whether a simple upload would conflict with an existing file."""
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    parent_id = data.get("parent", {}).get("id", "0")

    folder = db.session.get(Folder, parent_id)
    if not folder:
        return jsonify(
            {
                "type": "error",
                "status": 404,
                "code": "not_found",
                "message": "Parent folder not found",
            },
        ), 404

    existing = db.session.query(File).filter_by(folder_id=parent_id, name=name).first()
    if existing:
        return jsonify(
            {
                "type": "error",
                "status": 409,
                "code": "item_name_in_use",
                "message": "Item with name already exists",
                "context_info": {"conflicts": existing.to_dict()},
            },
        ), 409

    base_url = request.url_root.rstrip("/")
    return jsonify(
        {
            "upload_token": "dummy",
            "upload_url": f"{base_url}/2.0/files/content",
        },
    ), 200


@files_bp.route("/files/content", methods=["POST"])
def upload_file() -> tuple[Response, int]:
    """Upload a new file."""
    attributes = request.form.get("attributes")
    attrs = json.loads(attributes) if attributes else {}

    name = attrs.get("name", "unnamed_file")
    parent_id = attrs.get("parent", {}).get("id", "0")

    folder = db.session.get(Folder, parent_id)
    if not folder:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Parent folder not found",
            },
        ), 404

    content = extract_file_content()
    if content is None:
        return jsonify(
            {"type": "error", "code": "bad_request", "message": "No file provided"},
        ), 400

    file = File(
        name=name,
        folder_id=parent_id,
    )
    db.session.add(file)
    db.session.flush()
    create_version(file, content, name=name)
    db.session.commit()

    return jsonify({"entries": [file.to_dict()], "total_count": 1}), 201


@files_bp.route("/files/<file_id>/content", methods=["POST"])
def upload_file_version(file_id: str) -> tuple[Response, int]:
    """Upload a new version of an existing file."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404

    content = extract_file_content()
    if content is None:
        return jsonify(
            {"type": "error", "code": "bad_request", "message": "No file provided"},
        ), 400

    create_version(file, content)
    db.session.commit()

    return jsonify({"entries": [file.to_dict()], "total_count": 1}), 201


@files_bp.route("/files/<file_id>/copy", methods=["POST"])
def copy_file(file_id: str) -> tuple[Response, int]:
    """Copy a file to a new location."""
    file = db.session.get(File, file_id)
    if not file:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "File not found"},
        ), 404

    data = request.get_json()
    parent_id = data.get("parent", {}).get("id", file.folder_id)
    new_name = data.get("name", file.name)

    folder = db.session.get(Folder, parent_id)
    if not folder:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Destination folder not found",
            },
        ), 404

    current = file.current_version
    new_file = File(
        name=new_name,
        folder_id=parent_id,
    )
    db.session.add(new_file)
    db.session.flush()

    if current is not None:
        src_path = get_version_path(file.id, current.id)
        if src_path.exists():
            create_version(new_file, src_path.read_bytes(), name=new_name)

    db.session.commit()

    return jsonify(new_file.to_dict()), 201


@files_bp.route("/files/upload_sessions", methods=["POST"])
def preflight_check() -> tuple[Response, int]:
    """Preflight check for file upload (checks if name conflicts exist)."""
    data = request.get_json()
    name = data.get("name")
    parent_id = data.get("parent", {}).get("id", "0")

    folder = db.session.get(Folder, parent_id)
    if not folder:
        return jsonify(
            {"type": "error", "code": "not_found", "message": "Folder not found"},
        ), 404

    existing = db.session.query(File).filter_by(folder_id=parent_id, name=name).first()
    if existing:
        return jsonify(
            {
                "type": "error",
                "code": "item_name_in_use",
                "message": f"Item with name '{name}' already exists",
                "context_info": {
                    "conflicts": [{"id": existing.id, "name": existing.name}],
                },
            },
        ), 409

    return jsonify({"upload_token": str(uuid.uuid4())}), 200

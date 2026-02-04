"""Admin routes for browsing, health checks, and data reset."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from flask import (
    Blueprint,
    Response,
    g,
    jsonify,
    redirect,
    render_template_string,
    request,
)

from box_mock.db import DATA_DIR, get_session_class, reset_identity_data
from box_mock.models import Folder, SignRequest, User

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

admin_bp = Blueprint("admin", __name__)

BROWSE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Box Mock Browser</title>
<style>
  body { font-family: sans-serif; margin: 20px; }
  .identity-section { border: 1px solid #ccc; margin: 10px 0; padding: 15px; border-radius: 5px; }
  .identity-header { background: #f0f0f0; margin: -15px -15px 15px -15px; padding: 10px 15px; border-radius: 5px 5px 0 0; }
  .identity-header h2 { margin: 0; display: inline; }
  .folder-tree { margin-left: 20px; }
  h3 { margin-top: 15px; margin-bottom: 5px; }
</style>
</head>
<body>
<h1>Box Mock Browser</h1>
<p><a href="/_browse">Refresh</a></p>

{% macro render_folder(folder, indent=0) %}
<div style="margin-left: {{ indent * 20 }}px">
  <b>📁 {{ folder.name }}</b> <small>({{ folder.id }})</small>
  {% for file in folder.files %}
  <div style="margin-left: 20px">📄 {{ file.name }} <small>({{ file.id }}, {{ file.size }} bytes)</small></div>
  {% endfor %}
  {% for child in folder.children %}
  {{ render_folder(child, indent + 1) }}
  {% endfor %}
</div>
{% endmacro %}

{% if identities %}
{% for ident in identities %}
<div class="identity-section">
  <div class="identity-header">
    <h2>📦 {{ ident.name }}</h2>
    <form style="display:inline; float:right" method="POST" action="/_reset">
      <input type="hidden" name="identity" value="{{ ident.name }}">
      <button type="submit">Reset</button>
    </form>
  </div>
  
  <h3>Folders & Files</h3>
  {{ render_folder(ident.tree) }}
  
  <h3>Users ({{ ident.users|length }})</h3>
  {% if ident.users %}
  <ul>
  {% for user in ident.users %}
    <li>👤 <b>{{ user.name }}</b> ({{ user.id }}) - {{ user.email or 'no email' }}</li>
  {% endfor %}
  </ul>
  {% else %}
  <p><em>No users</em></p>
  {% endif %}
  
  <h3>Sign Requests ({{ ident.sign_requests|length }})</h3>
  {% if ident.sign_requests %}
  <ul>
  {% for sr in ident.sign_requests %}
    <li>✍️ <b>{{ sr.id }}</b> - Status: {{ sr.status }}
    {% if sr.signers %}
    <ul>
    {% for signer in sr.signers %}
      <li>{{ signer.email }} ({{ signer.role }})</li>
    {% endfor %}
    </ul>
    {% endif %}
    </li>
  {% endfor %}
  </ul>
  {% else %}
  <p><em>No sign requests</em></p>
  {% endif %}
</div>
{% endfor %}
{% else %}
<p>No identities found. Make a request with an Authorization header to create one.</p>
{% endif %}
</body>
</html>
"""  # noqa


def _get_tree(session: Session, folder: Folder) -> dict[str, Any]:
    """Recursively build folder tree structure."""
    return {
        "id": folder.id,
        "name": folder.name,
        "files": [{"id": f.id, "name": f.name, "size": f.size} for f in folder.files],
        "children": [_get_tree(session, child) for child in folder.children],
    }


def _get_identity_data(identity: str) -> dict[str, Any]:
    """Get all data for a specific identity."""
    session_class = get_session_class(identity)
    session = session_class()

    try:
        root = session.get(Folder, "0")
        tree = (
            _get_tree(session, root)
            if root
            else {"id": "0", "name": "Empty", "files": [], "children": []}
        )

        users = [
            {"id": u.id, "name": u.name, "email": u.email}
            for u in session.query(User).all()
        ]

        sign_requests = []
        for sr in session.query(SignRequest).all():
            signers = json.loads(sr.signers_json) if sr.signers_json else []
            sign_requests.append({"id": sr.id, "status": sr.status, "signers": signers})

        return {
            "name": identity,
            "tree": tree,
            "users": users,
            "sign_requests": sign_requests,
        }
    finally:
        session.close()


@admin_bp.route("/_browse")
def browse() -> str:
    """
    Render HTML view of all identities with their folders, files,
    and sign requests.
    """
    identities = (
        [
            _get_identity_data(identity_dir.name)
            for identity_dir in sorted(DATA_DIR.iterdir())
            if identity_dir.is_dir() and (identity_dir / "box.db").exists()
        ]
        if DATA_DIR.exists()
        else []
    )

    return render_template_string(BROWSE_TEMPLATE, identities=identities)


@admin_bp.route("/_reset", methods=["POST"])
def reset() -> tuple[Response, int] | Response:
    """Clear all data for the given identity (database + files)."""
    if request.is_json:
        data = request.get_json() or {}
        identity = data.get("identity") or g.get("identity", "default")
    else:
        identity = request.form.get("identity") or g.get("identity", "default")

    reset_identity_data(identity)

    if request.is_json:
        return jsonify({"status": "reset complete", "identity": identity}), 200

    return redirect("/_browse")


@admin_bp.route("/health")
def health() -> Response:
    """Health check endpoint."""
    return jsonify({"status": "ok"})

"""Sign request routes for Box Mock API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    jsonify,
    redirect,
    render_template_string,
    request,
)

from box_mock.db import db
from box_mock.models import File, Folder, SignRequest
from box_mock.routes.files import get_file_path

sign_requests_bp = Blueprint("sign_requests", __name__, url_prefix="/2.0")
sign_embed_bp = Blueprint("sign_embed", __name__)

UNSIGNED_TEXT = b"unsigned"


EMBED_FORM_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Box Mock Sign</title>
<style>
  body { font-family: sans-serif; max-width: 480px; margin: 60px auto; padding: 20px; }
  .card { border: 1px solid #ccc; border-radius: 8px; padding: 24px; }
  .error { color: #b00020; margin-bottom: 12px; }
  label { display: block; margin: 16px 0; }
  button { padding: 8px 16px; font-size: 14px; cursor: pointer; }
</style>
</head>
<body>
<div class="card">
  <h2>Sign Document</h2>
  <p>Signer: <b>{{ signer.email }}</b></p>
  <p>Sign request: <code>{{ sign_request_id }}</code></p>
  {% if error %}<div class="error">{{ error }}</div>{% endif %}
  <form method="POST">
    <label>
      <input type="checkbox" name="signed" value="1">
      I agree to sign this document
    </label>
    <button type="submit">Submit</button>
  </form>
</div>
</body>
</html>
"""


EMBED_DONE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Box Mock Sign - Done</title>
<style>
  body { font-family: sans-serif; max-width: 480px; margin: 60px auto; padding: 20px; }
  .card { border: 1px solid #ccc; border-radius: 8px; padding: 24px; }
</style>
</head>
<body>
<div class="card">
  <h2>Document Signed</h2>
  <p>Thanks, <b>{{ signer.email }}</b>. Your signature has been recorded.</p>
  <p>Sign request status: <b>{{ status }}</b></p>
</div>
</body>
</html>
"""


EMBED_ALREADY_SIGNED_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Box Mock Sign - Already Signed</title>
<style>
  body { font-family: sans-serif; max-width: 480px; margin: 60px auto; padding: 20px; }
  .card { border: 1px solid #ccc; border-radius: 8px; padding: 24px; }
</style>
</head>
<body>
<div class="card">
  <h2>Already Signed</h2>
  <p><b>{{ signer.email }}</b> already signed this document.</p>
</div>
</body>
</html>
"""


def _build_embed_url(sign_request_id: str, signer_token: str, identity: str) -> str:
    """Build a tenant-scoped embed URL for a signer."""
    base = (current_app.config.get("PUBLIC_BASE_URL") or request.url_root).rstrip("/")
    return (
        f"{base}/sign/{sign_request_id}/{signer_token}?access_token=Identity={identity}"
    )


def _find_signer(signers: list[dict], signer_token: str) -> dict | None:
    """Find a signer entry in the signers list by signer_token."""
    for signer in signers:
        if signer.get("signer_token") == signer_token:
            return signer
    return None


@sign_requests_bp.route("/sign_requests", methods=["POST"])
def create_sign_request() -> tuple[Response, int]:
    """Create a Box Sign request."""
    data = request.get_json() or {}

    signers_data = data.get("signers", [])
    parent_folder = data.get("parent_folder") or {}
    parent_folder_id = parent_folder.get("id", "0")
    redirect_url = data.get("redirect_url")

    folder = db.session.get(Folder, parent_folder_id)
    if not folder:
        return jsonify(
            {
                "type": "error",
                "code": "not_found",
                "message": "Parent folder not found",
            },
        ), 404

    sign_request_id = str(uuid.uuid4())
    identity = g.get("identity", "default")

    sign_file = File(
        name=f"sign_doc_{sign_request_id[:8]}.txt",
        folder_id=parent_folder_id,
        size=len(UNSIGNED_TEXT),
    )
    db.session.add(sign_file)
    db.session.commit()
    get_file_path(sign_file.id).write_bytes(UNSIGNED_TEXT)

    signers = []
    for s in signers_data:
        signer_token = str(uuid.uuid4())
        signers.append(
            {
                "type": "signer",
                "email": s.get("email"),
                "role": s.get("role", "signer"),
                "signer_token": signer_token,
                "embed_url": _build_embed_url(sign_request_id, signer_token, identity),
                "has_viewed_document": False,
                "signer_decision": None,
            }
        )

    files = [
        {
            "type": "file",
            "id": sign_file.id,
            "name": sign_file.name,
        }
    ]

    sign_request = SignRequest(
        id=sign_request_id,
        parent_folder_id=parent_folder_id,
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


@sign_embed_bp.route("/sign/<sign_request_id>/<signer_token>", methods=["GET"])
def render_embed_form(sign_request_id: str, signer_token: str) -> tuple[str, int] | str:
    """Render the embed signing form for a signer."""
    sign_request = db.session.get(SignRequest, sign_request_id)
    if not sign_request:
        return "Sign request not found", 404

    signers = json.loads(sign_request.signers_json or "[]")
    signer = _find_signer(signers, signer_token)
    if signer is None:
        return "Signer not found", 404

    if signer.get("signer_decision"):
        return render_template_string(EMBED_ALREADY_SIGNED_TEMPLATE, signer=signer)

    signer["has_viewed_document"] = True
    sign_request.signers_json = json.dumps(signers)
    db.session.commit()

    return render_template_string(
        EMBED_FORM_TEMPLATE,
        signer=signer,
        sign_request_id=sign_request_id,
        error=None,
    )


@sign_embed_bp.route("/sign/<sign_request_id>/<signer_token>", methods=["POST"])
def submit_embed_form(
    sign_request_id: str, signer_token: str
) -> tuple[str, int] | str | Response:
    """Process a signer's submission of the embed form."""
    sign_request = db.session.get(SignRequest, sign_request_id)
    if not sign_request:
        return "Sign request not found", 404

    signers = json.loads(sign_request.signers_json or "[]")
    signer = _find_signer(signers, signer_token)
    if signer is None:
        return "Signer not found", 404

    if signer.get("signer_decision"):
        return render_template_string(EMBED_ALREADY_SIGNED_TEMPLATE, signer=signer)

    if not request.form.get("signed"):
        return render_template_string(
            EMBED_FORM_TEMPLATE,
            signer=signer,
            sign_request_id=sign_request_id,
            error="You must check the box to sign.",
        )

    signer["signer_decision"] = {
        "type": "signed",
        "finalized_at": datetime.now(tz=UTC).isoformat(),
    }
    signer["has_viewed_document"] = True

    files = json.loads(sign_request.files_json or "[]")
    appended = f"\nsigned by {signer.get('email')}".encode()
    for entry in files:
        file = db.session.get(File, entry.get("id"))
        if file is None:
            continue
        file_path = get_file_path(file.id)
        existing = file_path.read_bytes() if file_path.exists() else b""
        new_content = existing + appended
        file_path.write_bytes(new_content)
        file.version = (file.version or 1) + 1
        file.size = len(new_content)

    sign_request.signers_json = json.dumps(signers)

    if all(s.get("signer_decision") for s in signers):
        sign_request.status = "signed"
        sign_request.finished_at = datetime.now(tz=UTC)

    db.session.commit()

    if sign_request.redirect_url and sign_request.status == "signed":
        return redirect(sign_request.redirect_url)

    return render_template_string(
        EMBED_DONE_TEMPLATE,
        signer=signer,
        status=sign_request.status,
    )

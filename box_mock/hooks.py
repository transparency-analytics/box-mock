"""Request hooks for logging, debugging, and database session management."""

from __future__ import annotations

from flask import current_app, g, request

from box_mock.db import get_session_class
from box_mock.identity import get_identity


def log_request() -> None:
    """Log incoming request details for debugging."""
    current_app.logger.info(f"REQUEST: {request.method} {request.path}")
    current_app.logger.info(f"Content-Type: {request.content_type}")
    current_app.logger.info(f"Form data: {dict(request.form)}")
    current_app.logger.info(f"Files: {list(request.files.keys())}")
    for key in request.files:
        f = request.files[key]
        current_app.logger.info(
            f"  - {key}: filename='{f.filename}', content_type='{f.content_type}'",
        )
    if request.is_json and request.data:
        current_app.logger.info(f"JSON: {request.get_json()}")


def setup_db_session() -> None:
    """Before request hook to setup database session."""
    g.identity = get_identity()
    session_class = get_session_class(g.identity)
    g.db_session = session_class()


def teardown_db_session(exception: BaseException | None = None) -> None:  # noqa: ARG001
    """Teardown hook to cleanup session."""
    session = g.pop("db_session", None)
    if session:
        session.close()

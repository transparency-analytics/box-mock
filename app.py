"""Box Mock API Server - Entry point for running the Flask application."""

import argparse
import uuid
from pathlib import Path

from flask import Flask, request
from flask.wrappers import Response

from box_mock.hooks import log_request, setup_db_session, teardown_db_session
from box_mock.routes.admin import admin_bp
from box_mock.routes.collaborations import collaborations_bp
from box_mock.routes.files import files_bp
from box_mock.routes.folders import folders_bp
from box_mock.routes.sign_requests import sign_requests_bp
from box_mock.routes.users import users_bp


def create_app(*, testing: bool = False) -> Flask:
    """
    Create Flask app with identity-based database isolation.

    Pass ``testing=True`` to use a fresh in-memory SQLite database instead of
    the on-disk store under ``/data``.  Each call with ``testing=True`` gets its
    own unique database so tests are automatically isolated without any
    monkeypatching.
    """
    app = Flask(__name__)

    if testing:
        import tempfile  # noqa: PLC0415

        # Unique URI so every create_app(testing=True) call gets its own DB.
        unique_id = uuid.uuid4().hex
        app.config["DB_URL"] = (
            f"sqlite:///file:testdb_{unique_id}?mode=memory&cache=shared&uri=true"
        )
        # File uploads go to a per-test temp directory.
        app.config["FILES_DIR"] = Path(tempfile.mkdtemp(prefix="box_mock_test_"))
    else:
        data_dir = Path("/data")
        data_dir.mkdir(parents=True, exist_ok=True)
        app.config["DATA_DIR"] = data_dir
    app.logger.setLevel("DEBUG")

    app.register_blueprint(admin_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(folders_bp)
    app.register_blueprint(files_bp)
    app.register_blueprint(collaborations_bp)
    app.register_blueprint(sign_requests_bp)

    app.before_request(setup_db_session)
    app.before_request(log_request)
    app.teardown_request(teardown_db_session)

    @app.after_request
    def add_cors_headers(response: Response) -> Response:
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
        requested_headers = request.headers.get("Access-Control-Request-Headers", "")
        response.headers["Access-Control-Allow-Headers"] = (
            requested_headers or "Authorization, Content-Type"
        )
        return response

    @app.route("/<path:path>", methods=["OPTIONS"])
    @app.route("/", methods=["OPTIONS"])
    def handle_options(_path: str = "") -> tuple[str, int]:
        return "", 204

    return app


def main() -> None:
    """Run the Box Mock API server."""
    parser = argparse.ArgumentParser(description="Box Mock API Server")
    parser.add_argument("--port", type=int, default=8888, help="Port to run on")
    args = parser.parse_args()

    app = create_app()
    app.run(host="0.0.0.0", port=args.port, debug=True)


if __name__ == "__main__":
    main()

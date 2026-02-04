"""Box Mock API Server - Entry point for running the Flask application."""

import argparse
from pathlib import Path

from flask import Flask

from box_mock.hooks import log_request, setup_db_session, teardown_db_session
from box_mock.routes.admin import admin_bp
from box_mock.routes.collaborations import collaborations_bp
from box_mock.routes.files import files_bp
from box_mock.routes.folders import folders_bp
from box_mock.routes.sign_requests import sign_requests_bp
from box_mock.routes.users import users_bp


def create_app() -> Flask:
    """Create Flask app with identity-based database isolation."""
    app = Flask(__name__)

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

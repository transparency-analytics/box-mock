"""Identity extraction from request headers."""

import re

from flask import request


def get_identity() -> str:
    """Extract identity from Authorization header or access_token query param."""
    auth = request.headers.get("Authorization", "")
    if not auth:
        auth = request.args.get("access_token", "")
    match = re.search(r"Identity=([^;]+)", auth)
    return match.group(1).strip() if match else "default"

"""Identity extraction from request headers."""

import re

from flask import request


def get_identity() -> str:
    """Extract identity from Authorization header."""
    auth = request.headers.get("Authorization", "")
    match = re.search(r"Identity=([^;]+)", auth)
    return match.group(1).strip() if match else "default"

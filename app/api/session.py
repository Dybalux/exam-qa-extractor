"""Browser session identity shared by the SPA-facing endpoints."""

import uuid

from fastapi import Request

COOKIE_NAME = "session_id"
COOKIE_MAX_AGE = 86400


def session_id_from_request(request: Request) -> str:
    """Return the ``session_id`` cookie, or a fresh UUID when it is missing."""
    return request.cookies.get(COOKIE_NAME, str(uuid.uuid4()))

"""Shared flash-redirect helper for page handlers.

Extracted from pages.py so exams.py can also use it. Both message
and msg_type are URL-encoded to prevent malformed redirect URLs
from special characters (``&``, ``#``, spaces, non-ASCII) in
dynamic error strings.
"""

import urllib.parse

from fastapi.responses import RedirectResponse


def redirect_with_flash(
    url: str, message: str, msg_type: str = "success"
) -> RedirectResponse:
    """Create a ``303 See Other`` redirect with a flash message in query params.

    Args:
        url: Target URL (may already contain query params).
        message: User-facing flash message (will be URL-encoded).
        msg_type: Flash category — ``success``, ``error``, ``warning``, ``info``.

    Returns:
        A ``RedirectResponse`` ready for the handler to return directly.
    """
    encoded_message = urllib.parse.quote(message, safe="")
    encoded_type = urllib.parse.quote(msg_type, safe="")
    separator = "&" if "?" in url else "?"
    redirect_url = f"{url}{separator}message={encoded_message}&type={encoded_type}"
    return RedirectResponse(url=redirect_url, status_code=303)

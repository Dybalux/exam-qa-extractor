"""Slugification utility for URL-friendly strings."""

import re
import unicodedata


def slugify(value: str) -> str:
    """Normalize and convert string to a URL-friendly slug.

    Args:
        value: The string to slugify.

    Returns:
        A URL-friendly slug.
    """
    normalized: str = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    cleaned: str = re.sub(r"[^\w\s-]", "", normalized).strip().lower()
    return re.sub(r"[-\s]+", "-", cleaned)

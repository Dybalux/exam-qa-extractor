"""Tests for _form_str and _form_str_or_none form extraction helpers.

Covers SDD change ``fix-mypy-baseline`` REQ-TYPE-2 scenarios.
"""

import io

import pytest
from starlette.datastructures import UploadFile

from app.api.pages import _form_str, _form_str_or_none


def _upload_file(filename: str = "evil.exe") -> UploadFile:
    return UploadFile(file=io.BytesIO(b"fake"), filename=filename)


class FakeFormData:
    """Minimal FormData-like dict for testing form helpers."""

    def __init__(self, data: dict):
        self._data = data

    def get(self, key: str, default=None):
        return self._data.get(key, default)


# ── _form_str ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "form_data,key,default,expected",
    [
        # Normal string input.
        ({"name": "hello"}, "name", "", "hello"),
        # Whitespace-only → stripped to empty string, returns that (not default).
        ({"name": "   "}, "name", "fallback", ""),
        # Key not present → returns default.
        ({}, "name", "fallback", "fallback"),
        # None value → returns default.
        ({"name": None}, "name", "fallback", "fallback"),
        # UploadFile under text-field name → returns default (REQ-TYPE-2 scenario 2).
        ({"name": _upload_file()}, "name", "fallback", "fallback"),
    ],
)
def test_form_str_parametrized(form_data, key, default, expected):
    form = FakeFormData(form_data)
    assert _form_str(form, key, default) == expected


def test_form_str_strips_and_returns_trimmed():
    form = FakeFormData({"name": "  ohai  "})
    assert _form_str(form, "name") == "ohai"


def test_form_str_default_default_is_empty_string():
    form = FakeFormData({})
    assert _form_str(form, "missing") == ""


# ── _form_str_or_none ──────────────────────────────────────────


@pytest.mark.parametrize(
    "form_data,key,expected",
    [
        # Normal string input.
        ({"name": "hello"}, "name", "hello"),
        # Whitespace-only string → None (accepted behavior change per design).
        ({"name": "   "}, "name", None),
        # Empty string → None.
        ({"name": ""}, "name", None),
        # Key not present → None.
        ({}, "name", None),
        # None value → None.
        ({"name": None}, "name", None),
        # UploadFile under text-field name → None (REQ-TYPE-2 scenario 2).
        ({"name": _upload_file()}, "name", None),
    ],
)
def test_form_str_or_none_parametrized(form_data, key, expected):
    form = FakeFormData(form_data)
    assert _form_str_or_none(form, key) == expected


def test_form_str_or_none_strips_and_returns_trimmed():
    form = FakeFormData({"name": "  hello  "})
    assert _form_str_or_none(form, "name") == "hello"

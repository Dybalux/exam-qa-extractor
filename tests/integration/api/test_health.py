"""Smoke tests for the health check endpoint."""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /health returns 200 with status: ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_list_exams_empty(client):
    """GET /api/v1/exams/ returns empty list on a fresh DB."""
    resp = await client.get("/api/v1/exams/")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_missing_exam_returns_404(client):
    """GET /api/v1/exams/999999 returns 404 with global handler shape."""
    resp = await client.get("/api/v1/exams/999999")
    assert resp.status_code == 404
    body = resp.json()
    assert "detail" in body
    assert body["detail"]

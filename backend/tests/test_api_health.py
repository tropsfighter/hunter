"""Tests for GET /health (and wrong-method behaviour on same path)."""

from __future__ import annotations

import pytest


@pytest.mark.endpoint("GET /health")
def test_health_ok_json(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


@pytest.mark.endpoint("GET /health")
def test_health_cache_headers_optional(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert "application/json" in r.headers.get("content-type", "")


@pytest.mark.endpoint("GET /health")
def test_health_post_method_not_allowed(client):
    r = client.post("/health", json={})
    assert r.status_code == 405


@pytest.mark.endpoint("GET /health")
def test_health_put_method_not_allowed(client):
    r = client.put("/health")
    assert r.status_code == 405

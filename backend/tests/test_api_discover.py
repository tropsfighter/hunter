"""Tests for POST /api/discover and GET /api/discover/status."""

from __future__ import annotations

import pytest

from hunter.storage.db import connect
from hunter.storage import queries as storeq


@pytest.mark.endpoint("POST /api/discover")
def test_discover_unknown_topic_returns_404(client):
    r = client.post(
        "/api/discover",
        json={"topic": "totally_unknown_topic_zz"},
    )
    assert r.status_code == 404
    assert "detail" in r.json()


@pytest.mark.endpoint("POST /api/discover")
def test_discover_accepts_known_topic_returns_202(client):
    client.put("/api/topics/discover_me", json={"queries": ["sample search"]})
    r = client.post(
        "/api/discover",
        json={
            "topic": "discover_me",
            "max_queries": 2,
            "max_results_per_query": 5,
            "max_total_videos": 10,
        },
    )
    assert r.status_code == 202
    body = r.json()
    assert body.get("topic") == "discover_me"
    assert body.get("started") is True


@pytest.mark.endpoint("POST /api/discover")
def test_discover_invalid_topic_pattern_returns_422(client):
    r = client.post(
        "/api/discover",
        json={"topic": "BadPattern!"},
    )
    assert r.status_code == 422


@pytest.mark.endpoint("POST /api/discover")
def test_discover_invalid_max_results_returns_422(client):
    client.put("/api/topics/discover_bounds", json={"queries": ["q"]})
    r = client.post(
        "/api/discover",
        json={"topic": "discover_bounds", "max_results_per_query": 0},
    )
    assert r.status_code == 422


@pytest.mark.endpoint("GET /api/discover/status")
def test_discover_status_empty_ok(client):
    r = client.get("/api/discover/status")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.endpoint("GET /api/discover/status")
def test_discover_status_returns_rows_after_manual_insert(client, db_path):
    conn = connect(db_path)
    rid = storeq.start_discovery_run(conn, "manual_topic")
    storeq.finish_discovery_run(
        conn,
        rid,
        queries_run=3,
        videos_upserted=10,
        channels_upserted=2,
    )
    conn.commit()
    conn.close()
    r = client.get("/api/discover/status")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) >= 1
    row = next(x for x in rows if x["topic"] == "manual_topic")
    assert row["queries_run"] == 3
    assert row["videos_upserted"] == 10
    assert row["channels_upserted"] == 2


@pytest.mark.endpoint("GET /api/discover/status")
def test_discover_status_limit_default_ok(client):
    r = client.get("/api/discover/status")
    assert r.status_code == 200


@pytest.mark.endpoint("GET /api/discover/status")
def test_discover_status_limit_boundary_1(client, db_path):
    conn = connect(db_path)
    storeq.start_discovery_run(conn, "lim1")
    conn.commit()
    conn.close()
    r = client.get("/api/discover/status", params={"limit": 1})
    assert r.status_code == 200
    assert len(r.json()) <= 1


@pytest.mark.endpoint("GET /api/discover/status")
def test_discover_status_limit_invalid_returns_422(client):
    r = client.get("/api/discover/status", params={"limit": 0})
    assert r.status_code == 422

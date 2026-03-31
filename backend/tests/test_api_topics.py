"""Tests for GET/PUT/DELETE /api/topics."""

from __future__ import annotations

import pytest

from hunter.storage.db import connect
from hunter.storage import queries as storeq


@pytest.mark.endpoint("GET /api/topics")
def test_list_topics_returns_list(client):
    r = client.get("/api/topics")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        row = data[0]
        assert "topic" in row and "query_count" in row and "queries" in row


@pytest.mark.endpoint("GET /api/topics")
def test_list_topics_reflects_delete(client):
    """Seeded topics cannot stay empty long-term (init_db re-seeds empty table); assert delete works."""
    client.put("/api/topics/ephemeral_list_topic", json={"queries": ["only for list test"]})
    names = {t["topic"] for t in client.get("/api/topics").json()}
    assert "ephemeral_list_topic" in names
    client.delete("/api/topics/ephemeral_list_topic")
    names_after = {t["topic"] for t in client.get("/api/topics").json()}
    assert "ephemeral_list_topic" not in names_after


@pytest.mark.endpoint("PUT /api/topics/{topic}")
def test_put_topic_creates_and_returns_queries(client):
    r = client.put(
        "/api/topics/test_topic_alpha",
        json={"queries": ["first query line", "second query"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["topic"] == "test_topic_alpha"
    assert body["query_count"] == 2
    assert body["queries"] == ["first query line", "second query"]


@pytest.mark.endpoint("PUT /api/topics/{topic}")
def test_put_topic_replaces_existing(client):
    client.put("/api/topics/test_topic_beta", json={"queries": ["old"]})
    r = client.put(
        "/api/topics/test_topic_beta",
        json={"queries": ["new one", "new two"]},
    )
    assert r.status_code == 200
    assert r.json()["query_count"] == 2


@pytest.mark.endpoint("PUT /api/topics/{topic}")
def test_put_topic_invalid_slug_returns_400(client):
    r = client.put(
        "/api/topics/Bad-Slug!",
        json={"queries": ["x"]},
    )
    assert r.status_code == 400
    assert "detail" in r.json()


@pytest.mark.endpoint("PUT /api/topics/{topic}")
def test_put_topic_empty_queries_returns_422(client):
    r = client.put("/api/topics/valid_slug", json={"queries": []})
    assert r.status_code == 422


@pytest.mark.endpoint("PUT /api/topics/{topic}")
def test_put_topic_only_whitespace_queries_returns_400(client):
    r = client.put(
        "/api/topics/ws_only",
        json={"queries": ["   ", "\t"]},
    )
    assert r.status_code == 400


@pytest.mark.endpoint("DELETE /api/topics/{topic}")
def test_delete_topic_unknown_returns_404(client):
    r = client.delete("/api/topics/nonexistent_topic_xyz")
    assert r.status_code == 404


@pytest.mark.endpoint("DELETE /api/topics/{topic}")
def test_delete_topic_success_returns_204(client):
    client.put("/api/topics/del_ok_topic", json={"queries": ["q"]})
    r = client.delete("/api/topics/del_ok_topic")
    assert r.status_code == 204
    assert r.content == b""


@pytest.mark.endpoint("DELETE /api/topics/{topic}")
def test_delete_topic_blocked_when_channel_scores_exist(client, db_path):
    client.put("/api/topics/del_blocked", json={"queries": ["q"]})
    conn = connect(db_path)
    storeq.upsert_channel(
        conn,
        channel_id="UC_block_del",
        title="Ch",
        description="",
        custom_url=None,
        subscriber_count=1,
        video_count=0,
        thumbnail_url=None,
    )
    storeq.upsert_channel_topic_score(conn, channel_id="UC_block_del", topic="del_blocked", score=1.0)
    conn.commit()
    conn.close()
    r = client.delete("/api/topics/del_blocked")
    assert r.status_code == 400
    assert "detail" in r.json()

"""Tests for GET /api/kols and GET /api/kols/export.csv."""

from __future__ import annotations

import csv
import io

import pytest

from hunter.storage.db import connect
from hunter.storage import queries as storeq


def _seed_two_channels(db_path, topic: str = "football_equipment") -> None:
    conn = connect(db_path)
    storeq.upsert_channel(
        conn,
        channel_id="UC_alpha_test",
        title="Alpha Channel Zebra",
        description="About football training",
        custom_url="@alpha",
        subscriber_count=1000,
        video_count=3,
        thumbnail_url=None,
    )
    storeq.upsert_channel_topic_score(conn, channel_id="UC_alpha_test", topic=topic, score=8.5)
    storeq.upsert_video(
        conn,
        video_id="vid1",
        channel_id="UC_alpha_test",
        title="Match review",
        description="Great game",
        published_at=None,
        view_count=100,
        topic=topic,
    )
    storeq.upsert_channel(
        conn,
        channel_id="UC_beta_test",
        title="Beta Wearables",
        description="Smart watch tips",
        custom_url=None,
        subscriber_count=500,
        video_count=1,
        thumbnail_url=None,
    )
    storeq.upsert_channel_topic_score(conn, channel_id="UC_beta_test", topic=topic, score=3.0)
    conn.commit()
    conn.close()


@pytest.mark.endpoint("GET /api/kols")
def test_kols_empty_ok(client):
    r = client.get("/api/kols")
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.endpoint("GET /api/kols")
def test_kols_with_data_returns_rows(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get("/api/kols", params={"topic": "football_equipment", "limit": 50})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    ids = {x["channel_id"] for x in rows}
    assert ids == {"UC_alpha_test", "UC_beta_test"}


@pytest.mark.endpoint("GET /api/kols")
def test_kols_topic_all_includes_rows(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get("/api/kols", params={"topic": "all", "limit": 50})
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.endpoint("GET /api/kols")
def test_kols_sort_subscribers(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols",
        params={"topic": "football_equipment", "sort": "subscribers", "limit": 10},
    )
    assert r.status_code == 200
    subs = [x["subscriber_count"] for x in r.json()]
    assert subs == sorted(subs, reverse=True)


@pytest.mark.endpoint("GET /api/kols")
def test_kols_sort_title(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols",
        params={"topic": "football_equipment", "sort": "title", "limit": 10},
    )
    assert r.status_code == 200
    titles = [x["title"] for x in r.json()]
    assert titles == sorted(titles, key=str.casefold)


@pytest.mark.endpoint("GET /api/kols")
def test_kols_sort_contact_returns_200(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols",
        params={"topic": "football_equipment", "sort": "contact", "limit": 10},
    )
    assert r.status_code == 200
    assert len(r.json()) == 2


@pytest.mark.endpoint("GET /api/kols")
def test_kols_invalid_sort_coerced_to_score(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols",
        params={"topic": "football_equipment", "sort": "not_a_real_sort", "limit": 10},
    )
    assert r.status_code == 200
    scores = [x["score"] for x in r.json()]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.endpoint("GET /api/kols")
def test_kols_search_filters(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols",
        params={"topic": "football_equipment", "search": "zebra", "limit": 10},
    )
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["channel_id"] == "UC_alpha_test"


@pytest.mark.endpoint("GET /api/kols")
def test_kols_limit_too_high_returns_422(client):
    r = client.get("/api/kols", params={"limit": 9999})
    assert r.status_code == 422


@pytest.mark.endpoint("GET /api/kols")
def test_kols_limit_zero_returns_422(client):
    r = client.get("/api/kols", params={"limit": 0})
    assert r.status_code == 422


@pytest.mark.endpoint("GET /api/kols")
def test_kols_cache_control_no_store(client):
    r = client.get("/api/kols")
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")


@pytest.mark.endpoint("GET /api/kols/export.csv")
def test_export_csv_headers_and_empty(client):
    r = client.get("/api/kols/export.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    assert "attachment" in r.headers.get("content-disposition", "")
    text = r.text
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert rows[0][0] == "channel_id"
    assert len(rows) == 1


@pytest.mark.endpoint("GET /api/kols/export.csv")
def test_export_csv_with_rows(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols/export.csv",
        params={"topic": "football_equipment", "limit": 10},
    )
    assert r.status_code == 200
    reader = csv.reader(io.StringIO(r.text))
    rows = list(reader)
    assert len(rows) == 3


@pytest.mark.endpoint("GET /api/kols/export.csv")
def test_export_csv_invalid_limit_returns_422(client):
    r = client.get("/api/kols/export.csv", params={"limit": 0})
    assert r.status_code == 422


@pytest.mark.endpoint("GET /api/kols/export.csv")
def test_export_csv_respects_search(client, db_path):
    client.put("/api/topics/football_equipment", json={"queries": ["q"]})
    _seed_two_channels(db_path, "football_equipment")
    r = client.get(
        "/api/kols/export.csv",
        params={"topic": "football_equipment", "search": "wearables", "limit": 50},
    )
    assert r.status_code == 200
    reader = csv.reader(io.StringIO(r.text))
    rows = list(reader)
    assert len(rows) == 2

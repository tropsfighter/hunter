"""Topic definitions (YouTube search query lists) stored in SQLite."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

import yaml

_TOPIC_SLUG = re.compile(r"^[a-z0-9_]{1,64}$")
_KEYWORDS_PATH = Path(__file__).resolve().parent.parent / "config" / "keywords.yaml"


def validate_topic_slug(topic: str) -> str:
    if not topic or not _TOPIC_SLUG.match(topic):
        raise ValueError("Topic must match ^[a-z0-9_]{1,64}$ (lowercase letters, digits, underscore).")
    return topic


def scoring_tokens_for_queries(queries: list[str]) -> list[str]:
    """Lowercase tokens from query strings for overlap scoring (same rules as legacy keywords)."""
    tokens: set[str] = set()
    for q in queries:
        for part in q.lower().replace("/", " ").split():
            if len(part) > 2:
                tokens.add(part)
    return sorted(tokens)


def list_topic_keys(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT topic FROM topic_queries ORDER BY topic").fetchall()
    return [str(r["topic"]) for r in rows]


def list_topics_summary(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT topic, queries_json FROM topic_queries ORDER BY topic",
    ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        qs = json.loads(r["queries_json"])
        out.append({"topic": r["topic"], "query_count": len(qs), "queries": qs})
    return out


def get_queries(conn: sqlite3.Connection, topic: str) -> list[str]:
    row = conn.execute(
        "SELECT queries_json FROM topic_queries WHERE topic = ?",
        (topic,),
    ).fetchone()
    if not row:
        return []
    data = json.loads(row["queries_json"])
    if not isinstance(data, list):
        return []
    return [str(q) for q in data if str(q).strip()]


def set_queries(conn: sqlite3.Connection, topic: str, queries: list[str]) -> None:
    validate_topic_slug(topic)
    cleaned = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
    if not cleaned:
        raise ValueError("At least one non-empty query string is required.")
    conn.execute(
        """
        INSERT INTO topic_queries (topic, queries_json, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(topic) DO UPDATE SET
            queries_json = excluded.queries_json,
            updated_at = datetime('now')
        """,
        (topic, json.dumps(cleaned)),
    )


def delete_topic(conn: sqlite3.Connection, topic: str) -> None:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM channel_topics WHERE topic = ?",
        (topic,),
    ).fetchone()
    if row and int(row["c"]) > 0:
        raise ValueError(
            "Cannot delete this topic while channels are still scored for it.",
        )
    cur = conn.execute("DELETE FROM topic_queries WHERE topic = ?", (topic,))
    if cur.rowcount == 0:
        raise KeyError(f"Unknown topic {topic!r}")


def seed_from_yaml_if_empty(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT COUNT(*) AS c FROM topic_queries").fetchone()
    if row and int(row["c"]) > 0:
        return
    raw = yaml.safe_load(_KEYWORDS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return
    for topic_key, queries in sorted(raw.items(), key=lambda x: str(x[0])):
        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            continue
        cleaned = [q.strip() for q in queries if q.strip()]
        if not cleaned:
            continue
        tid = str(topic_key)
        if not _TOPIC_SLUG.match(tid):
            continue
        conn.execute(
            """
            INSERT INTO topic_queries (topic, queries_json, updated_at)
            VALUES (?, ?, datetime('now'))
            """,
            (tid, json.dumps(cleaned)),
        )


def scoring_tokens_for_topic(conn: sqlite3.Connection, topic: str) -> list[str]:
    return scoring_tokens_for_queries(get_queries(conn, topic))

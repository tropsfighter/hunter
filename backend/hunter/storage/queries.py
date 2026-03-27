import sqlite3

from hunter.models.kol import KolOut
from hunter.utils.contact import extract_contact_detail


def _sql_like_pattern(substring: str) -> str:
    """LIKE pattern for case-insensitive match; % and _ in user input are literal (ESCAPE '\\')."""
    s = substring.strip().lower()
    s = s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{s}%"


def upsert_channel(
    conn: sqlite3.Connection,
    *,
    channel_id: str,
    title: str,
    description: str,
    custom_url: str | None,
    subscriber_count: int | None,
    video_count: int | None,
    thumbnail_url: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO channels (
            channel_id, title, description, custom_url,
            subscriber_count, video_count, thumbnail_url, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(channel_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            custom_url = excluded.custom_url,
            subscriber_count = COALESCE(excluded.subscriber_count, channels.subscriber_count),
            video_count = COALESCE(excluded.video_count, channels.video_count),
            thumbnail_url = COALESCE(excluded.thumbnail_url, channels.thumbnail_url),
            updated_at = datetime('now')
        """,
        (
            channel_id,
            title,
            description,
            custom_url,
            subscriber_count,
            video_count,
            thumbnail_url,
        ),
    )


def upsert_video(
    conn: sqlite3.Connection,
    *,
    video_id: str,
    channel_id: str,
    title: str,
    description: str,
    published_at: str | None,
    view_count: int | None,
    topic: str,
) -> None:
    conn.execute(
        """
        INSERT INTO videos (
            video_id, channel_id, title, description, published_at, view_count, topic
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            title = excluded.title,
            description = excluded.description,
            published_at = COALESCE(excluded.published_at, videos.published_at),
            view_count = COALESCE(excluded.view_count, videos.view_count),
            topic = excluded.topic
        """,
        (video_id, channel_id, title, description, published_at, view_count, topic),
    )


def upsert_channel_topic_score(
    conn: sqlite3.Connection,
    *,
    channel_id: str,
    topic: str,
    score: float,
) -> None:
    conn.execute(
        """
        INSERT INTO channel_topics (channel_id, topic, score, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(channel_id, topic) DO UPDATE SET
            score = excluded.score,
            updated_at = datetime('now')
        """,
        (channel_id, topic, score),
    )


def start_discovery_run(conn: sqlite3.Connection, topic: str) -> int:
    cur = conn.execute(
        "INSERT INTO discovery_runs (topic, started_at) VALUES (?, datetime('now'))",
        (topic,),
    )
    return int(cur.lastrowid)


def finish_discovery_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    queries_run: int,
    videos_upserted: int,
    channels_upserted: int,
) -> None:
    conn.execute(
        """
        UPDATE discovery_runs SET
            finished_at = datetime('now'),
            queries_run = ?,
            videos_upserted = ?,
            channels_upserted = ?
        WHERE id = ?
        """,
        (queries_run, videos_upserted, channels_upserted, run_id),
    )


def _kol_out_from_row(conn: sqlite3.Connection, r: sqlite3.Row) -> KolOut:
    cid = r["channel_id"]
    custom = r["custom_url"]
    url = (
        f"https://www.youtube.com/@{custom.lstrip('@')}"
        if custom
        else f"https://www.youtube.com/channel/{cid}"
    )
    desc = r["description"] or ""
    topic_row = str(r["topic"])
    video_text = video_descriptions_blob_for_contact(conn, cid, topic_row)
    contact = extract_contact_detail(desc, extra_text=video_text)
    return KolOut(
        channel_id=cid,
        title=r["title"] or "",
        description=desc,
        custom_url=custom,
        subscriber_count=r["subscriber_count"],
        video_count=r["video_count"],
        thumbnail_url=r["thumbnail_url"],
        topic=r["topic"],
        score=float(r["score"] or 0),
        youtube_url=url,
        contact_detail=contact,
    )


def _contact_sort_key(contact_detail: str) -> tuple[int, str]:
    t = (contact_detail or "").strip()
    if not t:
        return (1, "")
    return (0, t.casefold())


def list_kols(
    conn: sqlite3.Connection,
    *,
    topic: str | None,
    sort: str,
    limit: int,
    search: str | None = None,
) -> list[KolOut]:
    if sort == "subscribers":
        order_clause = "c.subscriber_count DESC, ct.score DESC"
    elif sort == "title":
        order_clause = "c.title COLLATE NOCASE ASC"
    elif sort == "contact":
        order_clause = "c.channel_id ASC"
    else:
        order_clause = "ct.score DESC, c.subscriber_count DESC"

    sort_contact = sort == "contact"

    conditions: list[str] = []
    params: list = []
    if topic is not None and topic != "" and topic != "all":
        conditions.append("ct.topic = ?")
        params.append(topic)

    q = (search or "").strip()
    if q:
        pat = _sql_like_pattern(q)
        conditions.append(
            """(
            LOWER(c.title) LIKE ? ESCAPE '\\'
            OR LOWER(COALESCE(c.description, '')) LIKE ? ESCAPE '\\'
            OR LOWER(COALESCE(c.custom_url, '')) LIKE ? ESCAPE '\\'
            OR LOWER(c.channel_id) LIKE ? ESCAPE '\\'
            OR EXISTS (
                SELECT 1 FROM videos v
                WHERE v.channel_id = c.channel_id AND v.topic = ct.topic
                AND (
                    LOWER(v.title) LIKE ? ESCAPE '\\'
                    OR LOWER(COALESCE(v.description, '')) LIKE ? ESCAPE '\\'
                )
            )
        )"""
        )
        params.extend([pat] * 6)

    where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    sql = f"""
        SELECT
            c.channel_id,
            c.title,
            c.description,
            c.custom_url,
            c.subscriber_count,
            c.video_count,
            c.thumbnail_url,
            ct.topic,
            ct.score
        FROM channel_topics ct
        JOIN channels c ON c.channel_id = ct.channel_id
        {where_clause}
        ORDER BY {order_clause}
    """
    if not sort_contact:
        sql += " LIMIT ?"
        params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    out = [_kol_out_from_row(conn, r) for r in rows]
    if sort_contact:
        out.sort(key=lambda k: _contact_sort_key(k.contact_detail))
        out = out[:limit]
    return out


def video_titles_for_channel_topic(
    conn: sqlite3.Connection,
    channel_id: str,
    topic: str,
) -> list[str]:
    rows = conn.execute(
        "SELECT title FROM videos WHERE channel_id = ? AND topic = ?",
        (channel_id, topic),
    ).fetchall()
    return [str(r["title"]) for r in rows if r["title"]]


def video_descriptions_blob_for_contact(
    conn: sqlite3.Connection,
    channel_id: str,
    topic: str,
    *,
    limit: int = 16,
) -> str:
    """Longer video descriptions often contain business email / link-in-bio (public)."""
    rows = conn.execute(
        """
        SELECT description FROM videos
        WHERE channel_id = ? AND topic = ?
          AND description IS NOT NULL AND TRIM(description) != ''
        ORDER BY LENGTH(description) DESC
        LIMIT ?
        """,
        (channel_id, topic, limit),
    ).fetchall()
    return "\n".join(str(r["description"]) for r in rows if r["description"])

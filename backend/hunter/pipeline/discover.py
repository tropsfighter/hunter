from __future__ import annotations

import logging
import time

from hunter.clients.youtube import (
    build_youtube_service,
    fetch_channels,
    fetch_videos,
    parse_channel_row,
    parse_video_row,
    search_video_ids,
)
from hunter.config.settings import Settings, get_settings
from hunter.scoring.rank import score_channel
from hunter.storage.db import db_session
from hunter.storage import queries as storeq
from hunter.storage import topics as topic_store

logger = logging.getLogger(__name__)


def run_discovery(
    topic: str,
    *,
    settings: Settings | None = None,
    max_queries: int | None = None,
    max_results_per_query: int = 15,
    max_total_videos: int = 120,
) -> dict[str, int | str]:
    settings = settings or get_settings()
    if not settings.youtube_api_key.strip():
        raise ValueError(
            "Missing YOUTUBE_API_KEY. Copy backend/.env.example to backend/.env and set the key.",
        )

    db_path = settings.hunter_db_path
    with db_session(db_path) as conn:
        queries_full = topic_store.get_queries(conn, topic)
        valid = topic_store.list_topic_keys(conn)
    if not queries_full:
        raise ValueError(f"Unknown topic {topic!r}. Valid: {', '.join(valid)}")

    queries = queries_full
    nq = max_queries if max_queries is not None else min(6, len(queries))
    queries = queries[:nq]

    service = build_youtube_service(settings.youtube_api_key.strip())
    seen_videos: set[str] = set()
    ordered_video_ids: list[str] = []

    for query in queries:
        ids = search_video_ids(service, query=query, max_results=max_results_per_query)
        time.sleep(0.25)
        for vid in ids:
            if vid not in seen_videos:
                seen_videos.add(vid)
                ordered_video_ids.append(vid)
            if len(ordered_video_ids) >= max_total_videos:
                break
        if len(ordered_video_ids) >= max_total_videos:
            break

    if not ordered_video_ids:
        return {"topic": topic, "videos": 0, "channels": 0, "queries": len(queries)}

    video_items = fetch_videos(service, ordered_video_ids)
    channel_ids: list[str] = []
    for vid in ordered_video_ids:
        item = video_items.get(vid)
        if not item:
            continue
        row = parse_video_row(item, topic)
        if row["channel_id"]:
            channel_ids.append(row["channel_id"])

    channel_unique = list(dict.fromkeys(channel_ids))
    channel_items = fetch_channels(service, channel_unique)

    channel_title_hint: dict[str, str] = {}
    for vid in ordered_video_ids:
        item = video_items.get(vid)
        if not item:
            continue
        pr = parse_video_row(item, topic)
        cid = pr["channel_id"]
        if not cid:
            continue
        title_hint = pr.get("channel_title") or ""
        if cid not in channel_title_hint and title_hint:
            channel_title_hint[cid] = title_hint

    videos_upserted = 0
    channels_upserted = 0

    with db_session(db_path) as conn:
        run_id = storeq.start_discovery_run(conn, topic)
        try:
            for cid in channel_unique:
                if cid in channel_items:
                    crow = parse_channel_row(channel_items[cid])
                    storeq.upsert_channel(conn, **crow)
                else:
                    storeq.upsert_channel(
                        conn,
                        channel_id=cid,
                        title=channel_title_hint.get(cid, ""),
                        description="",
                        custom_url=None,
                        subscriber_count=None,
                        video_count=None,
                        thumbnail_url=None,
                    )
                channels_upserted += 1

            for vid in ordered_video_ids:
                item = video_items.get(vid)
                if not item:
                    continue
                row = parse_video_row(item, topic)
                if not row["channel_id"]:
                    continue
                storeq.upsert_video(
                    conn,
                    video_id=row["video_id"],
                    channel_id=row["channel_id"],
                    title=row["title"],
                    description=row["description"],
                    published_at=row["published_at"],
                    view_count=row["view_count"],
                    topic=row["topic"],
                )
                videos_upserted += 1

            topic_tokens = topic_store.scoring_tokens_for_topic(conn, topic)
            for cid in channel_unique:
                if cid in channel_items:
                    crow = parse_channel_row(channel_items[cid])
                else:
                    crow = {
                        "channel_id": cid,
                        "title": channel_title_hint.get(cid, ""),
                        "description": "",
                        "custom_url": None,
                        "subscriber_count": None,
                        "video_count": None,
                        "thumbnail_url": None,
                    }
                titles = storeq.video_titles_for_channel_topic(conn, cid, topic)
                views: list[int] = []
                for vid in ordered_video_ids:
                    it = video_items.get(vid)
                    if not it:
                        continue
                    pr = parse_video_row(it, topic)
                    if pr["channel_id"] != cid:
                        continue
                    vc = pr["view_count"]
                    if vc is not None:
                        views.append(vc)
                avg_views = sum(views) / len(views) if views else 0.0
                s = score_channel(
                    title=crow["title"],
                    description=crow["description"],
                    video_titles=titles,
                    subscriber_count=crow["subscriber_count"],
                    avg_video_views=avg_views,
                    topic_tokens=topic_tokens,
                )
                storeq.upsert_channel_topic_score(conn, channel_id=cid, topic=topic, score=s)

            storeq.finish_discovery_run(
                conn,
                run_id,
                queries_run=len(queries),
                videos_upserted=videos_upserted,
                channels_upserted=channels_upserted,
            )
        except Exception:
            logger.exception("Discovery failed for topic=%s", topic)
            raise

    return {
        "topic": topic,
        "videos": videos_upserted,
        "channels": channels_upserted,
        "queries": len(queries),
    }

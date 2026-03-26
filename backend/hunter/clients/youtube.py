from __future__ import annotations

import logging
import time
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def build_youtube_service(api_key: str):
    return build("youtube", "v3", developerKey=api_key, cache_discovery=False)


def _retry_http(callable_, *, attempts: int = 4, base_delay: float = 1.0) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return callable_()
        except HttpError as e:
            last = e
            status = e.resp.status if e.resp else 0
            if status in (403, 429, 500, 503) and i < attempts - 1:
                delay = base_delay * (2**i)
                logger.warning("YouTube API HTTP %s, retry in %.1fs", status, delay)
                time.sleep(delay)
                continue
            raise
    assert last is not None
    raise last


def search_video_ids(service, *, query: str, max_results: int) -> list[str]:
    def call():
        return (
            service.search()
            .list(
                part="id",
                type="video",
                q=query,
                maxResults=max(1, min(max_results, 50)),
                order="relevance",
            )
            .execute()
        )

    resp = _retry_http(call)
    ids: list[str] = []
    for item in resp.get("items", []):
        vid = (item.get("id") or {}).get("videoId")
        if vid:
            ids.append(vid)
    return ids


def fetch_videos(service, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not video_ids:
        return out
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        vid_param = ",".join(chunk)

        def call(ids=vid_param):
            return service.videos().list(part="snippet,statistics", id=ids).execute()

        resp = _retry_http(call)
        for item in resp.get("items", []):
            out[item["id"]] = item
        time.sleep(0.1)
    return out


def fetch_channels(service, channel_ids: list[str]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not channel_ids:
        return out
    unique = list(dict.fromkeys(channel_ids))
    for i in range(0, len(unique), 50):
        chunk = unique[i : i + 50]
        cid_param = ",".join(chunk)

        def call(ids=cid_param):
            return service.channels().list(part="snippet,statistics", id=ids).execute()

        resp = _retry_http(call)
        for item in resp.get("items", []):
            out[item["id"]] = item
        time.sleep(0.1)
    return out


def parse_video_row(item: dict[str, Any], topic: str) -> dict[str, Any]:
    sn = item.get("snippet") or {}
    st = item.get("statistics") or {}
    channel_id = sn.get("channelId") or ""
    views = st.get("viewCount")
    return {
        "video_id": item["id"],
        "channel_id": channel_id,
        "channel_title": sn.get("channelTitle") or "",
        "title": sn.get("title") or "",
        "description": sn.get("description") or "",
        "published_at": sn.get("publishedAt"),
        "view_count": int(views) if views is not None and views != "" else None,
        "topic": topic,
    }


def parse_channel_row(item: dict[str, Any]) -> dict[str, Any]:
    sn = item.get("snippet") or {}
    st = item.get("statistics") or {}
    thumbs = (sn.get("thumbnails") or {}).get("high") or (sn.get("thumbnails") or {}).get(
        "default",
    )
    thumb_url = (thumbs or {}).get("url")
    subs = st.get("subscriberCount")
    vcount = st.get("videoCount")
    return {
        "channel_id": item["id"],
        "title": sn.get("title") or "",
        "description": sn.get("description") or "",
        "custom_url": sn.get("customUrl"),
        "subscriber_count": int(subs) if subs not in (None, "") else None,
        "video_count": int(vcount) if vcount not in (None, "") else None,
        "thumbnail_url": thumb_url,
    }

from __future__ import annotations

import csv
import io
import logging
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from hunter.config.settings import Settings, get_settings
from hunter.models.kol import KolOut
from hunter.models.topic_api import (
    DiscoverAccepted,
    DiscoverIn,
    DiscoveryRunOut,
    TopicDetailOut,
    TopicPutBody,
)
from hunter.pipeline.discover import run_discovery
from hunter.storage.db import connect, init_db
from hunter.storage import queries as storeq
from hunter.storage import topics as topic_store

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.settings = settings
    conn = connect(settings.hunter_db_path)
    try:
        init_db(conn)
        conn.commit()
    finally:
        conn.close()
    yield


app = FastAPI(title="hunter", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def db_conn(
    settings: Annotated[Settings, Depends(get_settings_dep)],
) -> Iterator[sqlite3.Connection]:
    conn = connect(settings.hunter_db_path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _run_discovery_background(
    *,
    topic: str,
    max_queries: int | None,
    max_results_per_query: int,
    max_total_videos: int,
) -> None:
    try:
        run_discovery(
            topic,
            max_queries=max_queries,
            max_results_per_query=max_results_per_query,
            max_total_videos=max_total_videos,
        )
    except Exception:
        logger.exception("Background discovery failed for topic=%s", topic)


@app.get("/api/topics", response_model=list[TopicDetailOut])
def list_topics(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
) -> list[TopicDetailOut]:
    rows = topic_store.list_topics_summary(conn)
    return [TopicDetailOut(**r) for r in rows]


@app.put("/api/topics/{topic}", response_model=TopicDetailOut)
def put_topic(
    topic: str,
    body: TopicPutBody,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
) -> TopicDetailOut:
    try:
        topic_store.validate_topic_slug(topic)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    try:
        topic_store.set_queries(conn, topic, body.queries)
        conn.commit()
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    qs = topic_store.get_queries(conn, topic)
    return TopicDetailOut(topic=topic, query_count=len(qs), queries=qs)


@app.delete("/api/topics/{topic}", status_code=status.HTTP_204_NO_CONTENT)
def delete_topic_route(
    topic: str,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
) -> None:
    try:
        topic_store.delete_topic(conn, topic)
        conn.commit()
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown topic") from None
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.post("/api/discover", response_model=DiscoverAccepted, status_code=status.HTTP_202_ACCEPTED)
def start_discover(
    body: DiscoverIn,
    background_tasks: BackgroundTasks,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
) -> DiscoverAccepted:
    if not topic_store.get_queries(conn, body.topic):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Unknown topic {body.topic!r}. Create it with PUT /api/topics/{{topic}} first.",
        )
    background_tasks.add_task(
        _run_discovery_background,
        topic=body.topic,
        max_queries=body.max_queries,
        max_results_per_query=body.max_results_per_query,
        max_total_videos=body.max_total_videos,
    )
    return DiscoverAccepted(topic=body.topic)


@app.get("/api/discover/status", response_model=list[DiscoveryRunOut])
def discover_status(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    limit: int = Query(default=30, ge=1, le=100),
) -> list[DiscoveryRunOut]:
    rows = storeq.list_discovery_runs(conn, limit=limit)
    out: list[DiscoveryRunOut] = []
    for r in rows:
        out.append(
            DiscoveryRunOut(
                id=int(r["id"]),
                topic=str(r["topic"]),
                started_at=str(r["started_at"]) if r["started_at"] else None,
                finished_at=str(r["finished_at"]) if r["finished_at"] else None,
                queries_run=int(r["queries_run"]),
                videos_upserted=int(r["videos_upserted"]),
                channels_upserted=int(r["channels_upserted"]),
            ),
        )
    return out


@app.get("/api/kols", response_model=list[KolOut])
def list_kols(
    response: Response,
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    topic: str | None = Query(
        default=None,
        description="Topic key, or omit / 'all' for every topic",
    ),
    sort: str = Query(
        default="score",
        description="score | subscribers | title | contact",
    ),
    limit: int = Query(default=100, ge=1, le=500),
    search: str | None = Query(
        default=None,
        max_length=200,
        description="Filter by text in channel fields or videos for this topic row",
    ),
) -> list[KolOut]:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    if sort not in ("score", "subscribers", "title", "contact"):
        sort = "score"
    return storeq.list_kols(conn, topic=topic, sort=sort, limit=limit, search=search)


@app.get("/api/kols/export.csv")
def export_kols_csv(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    topic: str | None = Query(default=None),
    sort: str = Query(default="score"),
    limit: int = Query(default=500, ge=1, le=2000),
    search: str | None = Query(default=None, max_length=200),
) -> Response:
    rows = storeq.list_kols(conn, topic=topic, sort=sort, limit=limit, search=search)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        [
            "channel_id",
            "title",
            "topic",
            "score",
            "subscriber_count",
            "video_count",
            "youtube_url",
            "contact_detail",
        ],
    )
    for r in rows:
        w.writerow(
            [
                r.channel_id,
                r.title,
                r.topic,
                r.score,
                r.subscriber_count or "",
                r.video_count or "",
                r.youtube_url,
                r.contact_detail,
            ],
        )
    body = buf.getvalue()
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="kols.csv"',
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )

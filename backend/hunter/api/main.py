from __future__ import annotations

import csv
import io
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from hunter.config.settings import Settings, get_settings
from hunter.models.kol import KolOut
from hunter.storage.db import connect, init_db
from hunter.storage import queries as storeq


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


@app.get("/api/kols", response_model=list[KolOut])
def list_kols(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    topic: str | None = Query(
        default=None,
        description="Topic key, or omit / 'all' for every topic",
    ),
    sort: str = Query(
        default="score",
        description="score | subscribers | title",
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[KolOut]:
    if sort not in ("score", "subscribers", "title"):
        sort = "score"
    return storeq.list_kols(conn, topic=topic, sort=sort, limit=limit)


@app.get("/api/kols/export.csv")
def export_kols_csv(
    conn: Annotated[sqlite3.Connection, Depends(db_conn)],
    topic: str | None = Query(default=None),
    sort: str = Query(default="score"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> Response:
    rows = storeq.list_kols(conn, topic=topic, sort=sort, limit=limit)
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
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="kols.csv"'},
    )

from pydantic import BaseModel, Field


class TopicDetailOut(BaseModel):
    topic: str
    query_count: int
    queries: list[str]


class TopicPutBody(BaseModel):
    queries: list[str] = Field(..., min_length=1)


class DiscoverIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    max_queries: int | None = Field(default=None, ge=1, le=50)
    max_results_per_query: int = Field(default=15, ge=1, le=50)
    max_total_videos: int = Field(default=120, ge=1, le=500)


class DiscoverAccepted(BaseModel):
    started: bool = True
    topic: str


class DiscoveryRunOut(BaseModel):
    id: int
    topic: str
    started_at: str | None
    finished_at: str | None
    queries_run: int
    videos_upserted: int
    channels_upserted: int

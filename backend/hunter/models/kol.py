from pydantic import BaseModel, Field


class KolOut(BaseModel):
    channel_id: str
    title: str
    description: str = ""
    custom_url: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    thumbnail_url: str | None = None
    topic: str
    score: float = Field(description="Heuristic KOL score for this topic")
    youtube_url: str
    contact_detail: str = Field(
        default="",
        description="Public email(s) from channel/video text only; empty if none",
    )

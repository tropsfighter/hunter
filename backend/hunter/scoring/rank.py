from __future__ import annotations

import math


def _tokenize(text: str) -> set[str]:
    return {t for t in text.lower().replace("/", " ").split() if len(t) > 2}


def keyword_overlap_score(corpus: str, topic_tokens: list[str]) -> float:
    if not topic_tokens:
        return 0.0
    doc = _tokenize(corpus)
    if not doc:
        return 0.0
    hits = sum(1 for t in topic_tokens if t in doc)
    return min(10.0, hits * 1.2)


def score_channel(
    *,
    title: str,
    description: str,
    video_titles: list[str],
    subscriber_count: int | None,
    avg_video_views: float,
    topic_tokens: list[str],
) -> float:
    corpus = " ".join([title, description, *video_titles])
    subs = float(subscriber_count or 0)
    views = max(avg_video_views, 0.0)
    subs_part = math.log10(subs + 1) * 2.2
    views_part = math.log10(views + 1) * 1.6
    kw_part = keyword_overlap_score(corpus, topic_tokens)
    return round(subs_part + views_part + kw_part, 4)

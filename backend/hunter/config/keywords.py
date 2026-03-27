"""Default YouTube search queries per topic (YAML).

At runtime, topics are stored in SQLite (`topic_queries`) and seeded from this file when
the table is empty. Use the API or `hunter.storage.topics` for programmatic access.
"""

from functools import lru_cache
from pathlib import Path

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent
_KEYWORDS_FILE = _CONFIG_DIR / "keywords.yaml"


@lru_cache
def load_keyword_queries() -> dict[str, list[str]]:
    raw = yaml.safe_load(_KEYWORDS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("keywords.yaml must be a mapping of topic -> list of queries")
    out: dict[str, list[str]] = {}
    for topic, queries in raw.items():
        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            raise ValueError(f"Topic {topic!r} must map to a list of strings")
        out[str(topic)] = [q.strip() for q in queries if q.strip()]
    return out


def topic_keys() -> list[str]:
    return sorted(load_keyword_queries().keys())


def queries_for_topic(topic: str) -> list[str]:
    data = load_keyword_queries()
    if topic not in data:
        raise KeyError(f"Unknown topic {topic!r}. Valid: {', '.join(data)}")
    return data[topic]


def all_scoring_tokens(topic: str) -> list[str]:
    """Lowercase tokens from topic queries for overlap scoring."""
    tokens: set[str] = set()
    for q in queries_for_topic(topic):
        for part in q.lower().replace("/", " ").split():
            if len(part) > 2:
                tokens.add(part)
    return sorted(tokens)

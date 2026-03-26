"""Extract public email addresses from channel/video text (YouTube has no contact API field)."""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _expand_obfuscated_emails(text: str) -> str:
    """Catch common 'name at domain dot com' patterns in public bios."""
    t = text
    t = re.sub(
        r"([a-zA-Z0-9._%+-]+)\s*\[at\]\s*([a-zA-Z0-9.-]+)\s*\[dot\]\s*([a-zA-Z]{2,})",
        r"\1@\2.\3",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r"([a-zA-Z0-9._%+-]+)\s+at\s+([a-zA-Z0-9.-]+)\s+dot\s+([a-zA-Z]{2,})\b",
        r"\1@\2.\3",
        t,
        flags=re.IGNORECASE,
    )
    return t


def _emails(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _EMAIL_RE.finditer(text):
        e = m.group(0).strip().lower()
        if e.endswith((".png", ".jpg", ".gif", ".webp")):
            continue
        if e not in seen:
            seen.add(e)
            out.append(m.group(0).strip())
        if len(out) >= 3:
            break
    return out


def extract_contact_detail(
    description: str,
    *,
    extra_text: str = "",
) -> str:
    """
    Return only email address(es) from public channel + video text, joined with " · ".
    No URLs or /about links. Empty string if none found.
    """
    chunks = [description or "", extra_text or ""]
    raw_corpus = "\n".join(c for c in chunks if c).strip()
    expanded = _expand_obfuscated_emails(raw_corpus)
    corpus = raw_corpus + "\n" + expanded

    emails = _emails(corpus)
    if not emails:
        return ""
    return " · ".join(emails)

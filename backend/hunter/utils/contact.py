"""Extract public emails and contact URLs from channel/video text (YouTube has no contact API field)."""

from __future__ import annotations

import re
from urllib.parse import unquote, urlparse

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_MAILTO_RE = re.compile(r"mailto:([^\s<>\"']+)", re.IGNORECASE)
# http(s) URLs; trim trailing junk in a second step
_URL_RE = re.compile(r"https?://[^\s<>\[\]()\"']+", re.IGNORECASE)
_WWW_HOST_RE = re.compile(r"\bwww\.[^\s<>\[\]()\"']+", re.IGNORECASE)

_MAX_EMAILS = 5
_MAX_URLS = 5
_MAX_PARTS = 10

# Hosts that are never useful as “contact” (player, CDN, same-platform).
_BLOCKED_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "ytimg.com",
    "ggpht.com",
    "googlevideo.com",
    "gstatic.com",
    "googleusercontent.com",
)

# Obvious commerce/affiliate noise (not primary creator contact).
_SHOPPING_HOST_PREFIXES = ("amazon.", "ebay.", "aliexpress.", "walmart.")


def _host_key(netloc: str) -> str:
    h = netloc.lower()
    if "@" in h:
        h = h.split("@")[-1]
    if h.startswith("www."):
        h = h[4:]
    return h


def _is_blocked_host(host: str) -> bool:
    h = _host_key(host)
    if not h:
        return True
    for suf in _BLOCKED_HOST_SUFFIXES:
        if h == suf or h.endswith("." + suf):
            return True
    if h == "amzn.to":
        return True
    for pref in _SHOPPING_HOST_PREFIXES:
        if h.startswith(pref):
            return True
    return False


def _trim_url(url: str) -> str:
    u = url.rstrip(".,;:!?*+)]}>\"'")
    if u.endswith(")") and "(" not in u:
        u = u[:-1].rstrip(".,;:!?*+)]}>\"'")
    return u


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


def _collect_emails(corpus: str, *, max_n: int) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    for m in _EMAIL_RE.finditer(corpus):
        raw = m.group(0).strip()
        low = raw.lower()
        if low.endswith((".png", ".jpg", ".gif", ".webp")):
            continue
        if low not in seen:
            seen.add(low)
            out.append(raw)
        if len(out) >= max_n:
            return out

    for m in _MAILTO_RE.finditer(corpus):
        raw_addr = m.group(1).split("?", 1)[0].strip()
        addr = unquote(raw_addr)
        if "@" not in addr or " " in addr or len(addr) < 5:
            continue
        low = addr.lower()
        if low.endswith((".png", ".jpg", ".gif", ".webp")):
            continue
        if low not in seen:
            seen.add(low)
            out.append(addr)
        if len(out) >= max_n:
            break

    return out


def _url_dedupe_key(url: str) -> str:
    p = urlparse(url)
    h = _host_key(p.netloc)
    path = (p.path or "").rstrip("/")
    return f"{h}{path}"


def _url_sort_key(url: str) -> tuple[int, str]:
    p = urlparse(url)
    h = _host_key(p.netloc)
    path = (p.path or "").lower()
    bio_hints = (
        "linktr.ee",
        "beacons.page",
        "beacons.ai",
        "stan.store",
        "bio.site",
        "taplink.cc",
        "carrd.co",
        "hoo.be",
        "lnk.bio",
        "solo.to",
    )
    if any(b in h for b in bio_hints):
        return (0, url)
    if h in ("wa.me", "api.whatsapp.com"):
        return (1, url)
    if "instagram.com" in h or h in ("x.com", "twitter.com") or "threads.net" in h or "tiktok.com" in h:
        return (2, url)
    if "facebook.com" in h or h == "fb.me" or "fb.com" in h:
        return (2, url)
    if "contact" in path or path.endswith("/about") or path == "/about":
        return (3, url)
    if "patreon.com" in h or "ko-fi.com" in h or "buymeacoffee.com" in h:
        return (4, url)
    return (5, url)


def _contact_urls(text: str, *, max_urls: int) -> list[str]:
    raw: list[str] = []
    for m in _URL_RE.finditer(text):
        u = _trim_url(m.group(0))
        if u:
            raw.append(u)
    for m in _WWW_HOST_RE.finditer(text):
        u = _trim_url("https://" + m.group(0))
        if u and u.startswith("https://"):
            raw.append(u)

    seen_keys: set[str] = set()
    candidates: list[str] = []
    for u in raw:
        p = urlparse(u)
        if p.scheme not in ("http", "https") or not p.netloc:
            continue
        if _is_blocked_host(p.netloc):
            continue
        k = _url_dedupe_key(u)
        if k in seen_keys:
            continue
        seen_keys.add(k)
        candidates.append(u)

    candidates.sort(key=_url_sort_key)
    return candidates[:max_urls]


def extract_contact_detail(
    description: str,
    *,
    extra_text: str = "",
) -> str:
    """
    Return public emails and contact-oriented URLs from channel + video text,
    joined with " · ". Emails first (plain + mailto:), then URLs (social, link-in-bio,
    /contact, etc.). Empty string if nothing found.
    """
    chunks = [description or "", extra_text or ""]
    raw_corpus = "\n".join(c for c in chunks if c).strip()
    expanded = _expand_obfuscated_emails(raw_corpus)
    corpus = raw_corpus + "\n" + expanded

    email_parts = _collect_emails(corpus, max_n=_MAX_EMAILS)

    url_budget = max(0, min(_MAX_URLS, _MAX_PARTS - len(email_parts)))
    url_parts = _contact_urls(corpus, max_urls=url_budget) if url_budget else []

    parts = email_parts + url_parts
    if not parts:
        return ""
    return " · ".join(parts)

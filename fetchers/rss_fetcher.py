"""
RSS Fetcher — parses all configured RSS feeds and returns raw article dicts.
"""

import feedparser
import requests
import logging
from datetime import datetime, timezone, timedelta
from dateutil import parser as dateparser
from concurrent.futures import ThreadPoolExecutor, as_completed

from config.settings import RSS_FEEDS, NEWS_LOOKBACK_HOURS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TechNewsBot/1.0; +https://yourcompany.com/bot)"
}


def _fetch_one_feed(feed_cfg: dict) -> list[dict]:
    """Fetch and parse a single RSS feed."""
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)

    try:
        resp = requests.get(feed_cfg["url"], headers=HEADERS, timeout=15)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)

        for entry in feed.entries:
            # ── Parse publish date ──────────────────────────────────────────
            pub_date = None
            for attr in ("published", "updated", "created"):
                raw = getattr(entry, attr, None)
                if raw:
                    try:
                        pub_date = dateparser.parse(raw)
                        if pub_date and pub_date.tzinfo is None:
                            pub_date = pub_date.replace(tzinfo=timezone.utc)
                        break
                    except Exception:
                        continue

            if pub_date is None:
                pub_date = datetime.now(timezone.utc)

            # ── Age filter: skip articles older than lookback window ─────────
            if pub_date < cutoff:
                continue

            # ── Extract description / summary ───────────────────────────────
            summary = ""
            if hasattr(entry, "summary"):
                summary = entry.summary or ""
            elif hasattr(entry, "description"):
                summary = entry.description or ""

            # ── Extract image ───────────────────────────────────────────────
            image_url = _extract_image(entry)

            articles.append({
                "title":       entry.get("title", "").strip(),
                "url":         entry.get("link", "").strip(),
                "source":      feed_cfg["source"],
                "source_tier": feed_cfg.get("tier", 2),
                "published_at": pub_date,
                "summary":     summary,
                "image_url":   image_url,
                "content":     "",   # enriched later
                "fetch_type":  "rss",
            })

    except Exception as e:
        logger.warning(f"[RSS] Failed to fetch {feed_cfg['url']}: {e}")

    return articles


def _extract_image(entry) -> str:
    """Try multiple locations to find an article image."""
    # 1. media:content
    media = getattr(entry, "media_content", [])
    for m in media:
        if m.get("medium") == "image" and m.get("url"):
            return m["url"]

    # 2. media:thumbnail
    thumb = getattr(entry, "media_thumbnail", [])
    if thumb:
        return thumb[0].get("url", "")

    # 3. enclosures
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image"):
            return enc.get("href", "")

    # 4. og:image in content
    content = getattr(entry, "content", [])
    if content:
        import re
        m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content[0].get("value", ""))
        if m:
            return m.group(1)

    return ""


def fetch_all_rss() -> list[dict]:
    """Fetch all RSS feeds concurrently. Returns list of article dicts."""
    all_articles = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_one_feed, cfg): cfg for cfg in RSS_FEEDS}
        for future in as_completed(futures):
            try:
                all_articles.extend(future.result())
            except Exception as e:
                logger.error(f"[RSS] Thread error: {e}")

    logger.info(f"[RSS] Fetched {len(all_articles)} raw articles from {len(RSS_FEEDS)} feeds")
    return all_articles

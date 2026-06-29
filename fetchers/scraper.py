"""
Web Scraper — scrapes configured websites and returns article dicts.
Uses site-specific extractors where needed, falls back to trafilatura.
"""

import requests
import logging
import re
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

from config.settings import SCRAPE_TARGETS, NEWS_LOOKBACK_HOURS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# ─── Generic extractor ────────────────────────────────────────────────────────

def _generic_extract(url: str, source: str, tier: int) -> list[dict]:
    """Generic article list extractor — works on most news listing pages."""
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find article links — look for article tags, h2/h3 with links, or card divs
        candidates = []

        # Strategy 1: <article> tags
        for art in soup.find_all("article"):
            a = art.find("a", href=True)
            title_el = art.find(["h1", "h2", "h3", "h4"])
            if a and title_el:
                candidates.append({
                    "title": title_el.get_text(strip=True),
                    "url":   _abs_url(a["href"], url),
                    "el":    art,
                })

        # Strategy 2: heading + link combos
        if len(candidates) < 3:
            for h in soup.find_all(["h2", "h3"]):
                a = h.find("a", href=True) or h.find_parent("a")
                if a:
                    href = a.get("href", "")
                    if href and not href.startswith("#"):
                        candidates.append({
                            "title": h.get_text(strip=True),
                            "url":   _abs_url(href, url),
                            "el":    h,
                        })

        seen_urls = set()
        for c in candidates[:40]:
            art_url = c["url"]
            if not art_url or art_url in seen_urls:
                continue
            if not art_url.startswith("http"):
                continue
            seen_urls.add(art_url)

            # Find image in parent element
            img_url = ""
            parent = c["el"].find_parent(["article", "div", "li"])
            if parent:
                img = parent.find("img")
                if img:
                    img_url = img.get("src", img.get("data-src", ""))
                    if img_url:
                        img_url = _abs_url(img_url, url)

            # Use published date from element or default to now
            pub_date = _parse_date_from_element(c["el"]) or datetime.now(timezone.utc)

            if pub_date < cutoff:
                continue

            articles.append({
                "title":        c["title"],
                "url":          art_url,
                "source":       source,
                "source_tier":  tier,
                "published_at": pub_date,
                "summary":      "",
                "image_url":    img_url,
                "content":      "",
                "fetch_type":   "scrape",
            })

    except Exception as e:
        logger.warning(f"[Scraper] Failed {url}: {e}")

    return articles


def _parse_date_from_element(el) -> datetime | None:
    """Try to find a date/time inside an element."""
    time_el = el.find("time")
    if time_el:
        dt_str = time_el.get("datetime") or time_el.get_text(strip=True)
        try:
            from dateutil import parser as dp
            dt = dp.parse(dt_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            pass
    return None


def _abs_url(href: str, base: str) -> str:
    """Make href absolute using base URL."""
    if href.startswith("http"):
        return href
    from urllib.parse import urljoin
    return urljoin(base, href)


# ─── Site-specific: STPI ──────────────────────────────────────────────────────

def _stpi_extract(url: str, source: str, tier: int) -> list[dict]:
    """STPI-specific extractor."""
    articles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, verify=False)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for item in soup.select(".news-item, .event-item, .views-row, article"):
            title_el = item.find(["h2", "h3", "h4", "a"])
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            a = item.find("a", href=True)
            link = _abs_url(a["href"], url) if a else url

            pub_date = _parse_date_from_element(item) or datetime.now(timezone.utc)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
            if pub_date < cutoff:
                continue

            img = item.find("img")
            img_url = _abs_url(img["src"], url) if img and img.get("src") else ""

            articles.append({
                "title":        title,
                "url":          link,
                "source":       source,
                "source_tier":  tier,
                "published_at": pub_date,
                "summary":      "",
                "image_url":    img_url,
                "content":      "",
                "fetch_type":   "scrape",
            })
    except Exception as e:
        logger.warning(f"[Scraper/STPI] Failed {url}: {e}")
    return articles


# ─── Dispatch ─────────────────────────────────────────────────────────────────

def _scrape_one(target: dict) -> list[dict]:
    stype = target.get("type", "generic")
    if stype == "stpi":
        return _stpi_extract(target["url"], target["source"], target.get("tier", 2))
    return _generic_extract(target["url"], target["source"], target.get("tier", 2))


def fetch_all_scraped() -> list[dict]:
    """Scrape all configured websites concurrently."""
    all_articles = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_scrape_one, t): t for t in SCRAPE_TARGETS}
        for future in as_completed(futures):
            try:
                all_articles.extend(future.result())
            except Exception as e:
                logger.error(f"[Scraper] Thread error: {e}")

    logger.info(f"[Scraper] Fetched {len(all_articles)} raw articles from {len(SCRAPE_TARGETS)} sites")
    return all_articles

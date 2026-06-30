"""
Content Enricher — fetches full article body text from each article URL.
Uses trafilatura (best accuracy) with newspaper3k as fallback.
Full text is needed for:
  1. Semantic duplicate detection (TF-IDF on body, not just title)
  2. LLM relevance scoring (model reads full content, not just headline)

Also fetches a CONTENT-RELEVANT thumbnail image using the article title
as a search keyword — image is saved directly to generated_cards/ folder.
"""

import requests
import logging
import re
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    from newspaper import Article
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

THUMB_DIR = Path("generated_cards")
THUMB_DIR.mkdir(exist_ok=True)

# ── Minimum acceptable image dimensions ──────────────────────────────────────
MIN_IMG_W = 300
MIN_IMG_H = 180


def _title_slug(title: str) -> str:
    """Short hash of title — used as thumbnail filename."""
    return "thumb_" + hashlib.md5(title.encode()).hexdigest()[:12]


def _build_search_keywords(title: str) -> str:
    """
    Strip common filler words from title to build a tight image search query.
    Keep proper nouns, tech terms, product names.
    """
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "from", "is", "are", "was", "were",
        "has", "have", "had", "be", "been", "its", "it", "this", "that",
        "as", "will", "how", "why", "what", "who", "when", "new", "says",
        "after", "over", "up", "out", "about", "into", "than", "more",
        "now", "can", "could", "would", "should", "may", "might",
    }
    words = re.sub(r"[^\w\s]", " ", title).split()
    keywords = [w for w in words if w.lower() not in stopwords and len(w) > 2]
    # Take top 5 most meaningful words
    return " ".join(keywords[:5])


def _search_ddg_image(query: str) -> str | None:
    """
    Search DuckDuckGo Images for a relevant image URL.
    Uses the DDG image search JSON endpoint (no API key needed).
    Returns the first suitable image URL or None.
    """
    try:
        # Step 1: Get vqd token from DDG
        resp = requests.get(
            "https://duckduckgo.com/",
            params={"q": query, "iax": "images", "ia": "images"},
            headers=HEADERS,
            timeout=10,
        )
        vqd_match = re.search(r'vqd=(["\'])([^"\']+)\1', resp.text)
        if not vqd_match:
            vqd_match = re.search(r'"vqd"\s*:\s*"([^"]+)"', resp.text)
            vqd = vqd_match.group(1) if vqd_match else None
        else:
            vqd = vqd_match.group(2)

        if not vqd:
            logger.debug(f"[Enricher] DDG vqd token not found for: {query}")
            return None

        # Step 2: Fetch image results
        img_resp = requests.get(
            "https://duckduckgo.com/i.js",
            params={
                "q": query,
                "o": "json",
                "p": "1",
                "s": "0",
                "u": "bing",
                "f": ",,,,,",
                "l": "us-en",
                "vqd": vqd,
            },
            headers={**HEADERS, "Referer": "https://duckduckgo.com/"},
            timeout=10,
        )
        data = img_resp.json()
        results = data.get("results", [])

        for r in results[:8]:
            url    = r.get("image", "")
            width  = r.get("width", 0)
            height = r.get("height", 0)
            if url and width >= MIN_IMG_W and height >= MIN_IMG_H:
                # Skip obvious logos / icons by URL signals
                url_lower = url.lower()
                if any(s in url_lower for s in ["logo", "icon", "favicon", "avatar", "placeholder"]):
                    continue
                return url

    except Exception as e:
        logger.debug(f"[Enricher] DDG image search failed for '{query}': {e}")

    return None


def _download_and_save_thumb(url: str, slug: str) -> str | None:
    """
    Download image from URL, validate dimensions, save to generated_cards/.
    Returns saved file path or None.
    """
    out_path = THUMB_DIR / f"{slug}.jpg"
    if out_path.exists():
        return str(out_path)

    try:
        from PIL import Image
        r = requests.get(url, timeout=12, headers=HEADERS)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")

        # Final size validation
        if img.width < MIN_IMG_W or img.height < MIN_IMG_H:
            return None

        # Reject extreme aspect ratios (banners, strips)
        aspect = img.width / max(img.height, 1)
        if aspect < 0.4 or aspect > 5.5:
            return None

        img.save(str(out_path), "JPEG", quality=85, optimize=True)
        return str(out_path)

    except Exception as e:
        logger.debug(f"[Enricher] Thumb download failed {url}: {e}")
        return None


def _fetch_content_thumbnail(article: dict) -> dict:
    """
    Fetch a thumbnail relevant to the article.
    Priority order:
      1. og:image from the article page itself (BEST — article-specific)
      2. DuckDuckGo image search on article title keywords (fallback)
    Saves result to generated_cards/ and stores path in article["thumb_path"].
    """
    title = (article.get("title") or "").strip()
    if not title:
        return article

    slug = _title_slug(title)
    out_path = THUMB_DIR / f"{slug}.jpg"

    # Already fetched in a previous run
    if out_path.exists():
        article["thumb_path"] = str(out_path)
        return article

    saved = None

    # ── 1. PRIORITY 1: Try og:image from the article page (USE THIS FIRST!) ──
    og_url = article.get("image_url", "")
    if og_url and not og_url.startswith("data:"):
        og_lower = og_url.lower()

        # STRICT: Reject only obvious logos/icons/defaults
        logo_signals = ["logo", "icon", "favicon", "avatar", "placeholder",
                        "default-image", "fallback", "og-default",
                        "site-logo", "header-logo", "banner-logo", "watermark"]
        is_logo = any(s in og_lower for s in logo_signals)

        if not is_logo:
            saved = _download_and_save_thumb(og_url, slug)
            if saved:
                logger.info(f"[Enricher] ✅ Using article's og:image: {title[:50]}")
                article["thumb_path"] = saved
                return article
            else:
                logger.debug(f"[Enricher] og:image validation failed (too small/wrong aspect): {og_url[:80]}")

    # ── 2. FALLBACK: DuckDuckGo image search on article title ────────────────
    keywords = _build_search_keywords(title)
    if keywords:
        logger.debug(f"[Enricher] og:image missing/invalid. Searching DDG for: {keywords}")
        img_url = _search_ddg_image(keywords)
        if img_url:
            saved = _download_and_save_thumb(img_url, slug)
            if saved:
                logger.info(f"[Enricher] ✅ DDG image found for: {title[:50]}")
                article["thumb_path"] = saved
                return article

    # ── 3. No thumbnail found ─────────────────────────────────────────────────
    article["thumb_path"] = ""
    logger.debug(f"[Enricher] ⚠️  No thumbnail (og:image + DDG) for: {title[:50]}")

    return article


def _fetch_article_content(article: dict, fetch_thumbnail: bool = False) -> dict:

    url = article.get("url", "")
    if not url:
        return article

    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        html = resp.text

        # ── 1. Extract text via trafilatura ──────────────────────────────────
        text = ""
        if HAS_TRAFILATURA:
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            ) or ""

        # ── 2. Fallback: newspaper3k ─────────────────────────────────────────
        if not text and HAS_NEWSPAPER:
            try:
                art = Article(url)
                art.set_html(html)
                art.parse()
                text = art.text or ""
                if not article.get("image_url") and art.top_image:
                    article["image_url"] = art.top_image
            except Exception:
                pass

        # ── 3. Fallback: bare BeautifulSoup paragraph extraction ─────────────
        if not text:
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            paragraphs = soup.find_all("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs[:30])

        # ── 4. Try to grab og:image if we don't have one ─────────────────────
        if not article.get("image_url"):
            soup = BeautifulSoup(html, "html.parser")
            og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
            if og:
                article["image_url"] = og.get("content", "")

        # ── 5. Also grab og:description as backup summary ─────────────────────
        if not article.get("summary"):
            soup = BeautifulSoup(html, "html.parser")
            og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
            if og_desc:
                article["summary"] = og_desc.get("content", "")

        article["content"] = _clean_text(text)

    except Exception as e:
        logger.debug(f"[Enricher] Could not fetch content for {url}: {e}")
        article["content"] = article.get("summary", "")

    # ── 6. Fetch thumbnail ONLY if requested ──────────────────────────────────
    if fetch_thumbnail:
        article = _fetch_content_thumbnail(article)

    return article


def _clean_text(text: str) -> str:
    """Normalize and clean extracted text."""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # remove non-ASCII noise
    return text.strip()


def generate_thumbnails_for_articles(articles: list[dict], max_workers: int = 8) -> list[dict]:
    """
    Generate thumbnails ONLY for provided articles.
    This is called after filtering/scoring to create thumbnails for final articles only.
    """
    if not articles:
        return articles

    logger.info(f"[Enricher] Generating thumbnails for {len(articles)} final articles...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_content_thumbnail, art): art for art in articles}
        results = []
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"[Enricher] Thumbnail error: {e}")

    # Sort back to original order
    url_order = {art["url"]: i for i, art in enumerate(articles)}
    results.sort(key=lambda a: url_order.get(a["url"], 9999))

    thumbnail_count = sum(1 for a in results if a.get('thumb_path'))
    logger.info(f"[Enricher] ✅ Generated thumbnails for {thumbnail_count}/{len(results)} articles")

    return results


def enrich_articles(articles: list[dict], max_workers: int = 8, skip_thumbnails: bool = False) -> list[dict]:
  
    logger.info(f"[Enricher] Fetching full content for {len(articles)} articles...")
    if skip_thumbnails:
        logger.info(f"[Enricher] Thumbnail generation SKIPPED (will be generated later for final articles only)")

    enriched = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_article_content, art): art for art in articles}
        for future in as_completed(futures):
            try:
                enriched.append(future.result())
            except Exception as e:
                logger.error(f"[Enricher] Error: {e}")

    # Sort back to original order by URL (threading scrambles order)
    url_order = {art["url"]: i for i, art in enumerate(articles)}
    enriched.sort(key=lambda a: url_order.get(a["url"], 9999))

    logger.info(f"[Enricher] Content fetched. Articles with body text: "
                f"{sum(1 for a in enriched if len(a.get('content','')) > 200)}")

    if not skip_thumbnails:
        logger.info(f"[Enricher] Articles with thumbnails: "
                    f"{sum(1 for a in enriched if a.get('thumb_path'))}")

    return enriched